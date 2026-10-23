import logging

from breedgraph.domain.model import DatasetScope

logger = logging.getLogger(__name__)

from ..registry import handlers

from breedgraph.service_layer.infrastructure import AbstractStateStore, AbstractUnitOfWorkFactory

from breedgraph.domain import events
from breedgraph.domain.model.submissions import SubmissionStatus
from breedgraph.domain.model.errors import ItemError
from breedgraph.domain.model.programs import GroupingScope
from breedgraph.domain.model.contributions import contributions_from
from breedgraph.domain.model.controls import Access, ControlledModelLabel
from breedgraph.service_layer.application.contributions import verify_contributions

from breedgraph.domain.importers import DatasetImport, DatasetRecordsImport, DatasetUpdateImport

@handlers.event_handler()
async def handle_dataset_submitted(
        event: events.datasets.DatasetSubmitted,
        state_store: AbstractStateStore,
        uow_factory: AbstractUnitOfWorkFactory
):
    async with (uow_factory.get_uow(user_id=event.agent_id, write_team=event.write_team, release=event.release) as uow):
        try:
            await state_store.set_submission_status(event.submission_id, SubmissionStatus.PROCESSING)
            submission = await state_store.get_submission_data(agent_id=event.agent_id, submission_id=event.submission_id)

            dataset_import = DatasetImport(**submission)
            dataset_input = dataset_import.to_input_for_create()
            # Programs are loaded whole, so check the study can be read before linking to it
            await uow.controls.require_access(ControlledModelLabel.STUDY, [dataset_input.study], Access.READ)
            # a new dataset is of a variable or factor of the current ontology
            await uow.ontology.require_entries([dataset_input.concept])
            await verify_contributions(uow, dataset_input.contributions)
            await uow.controls.require_read(ControlledModelLabel.REFERENCE, [
                *(dataset_input.references or []),
                *(reference_id for record in dataset_input.records for reference_id in record.references or [])
            ])
            # each record is on a unit the user can read: another, or one that isn't there, is not found
            await uow.controls.require_read(ControlledModelLabel.UNIT, [record.unit for record in dataset_input.records])

            program = await uow.repositories.programs.get(study_id=dataset_input.study)
            if program is None:
                raise ValueError(f"Study not found {dataset_import.study_id}")

            study = program.get_study(dataset_import.study_id)

            # The records are parsed into the new dataset, which is then created with them: creating needs write
            # access, where adding them to a stored dataset would be a change to it, needing curate access. A record
            # that doesn't parse is reported by its index, and nothing is stored.
            dataset_input.records = list()
            scale = await uow.ontology.get_concept_scale(dataset_import.concept_id)
            item_errors = [
                ItemError(index=i, error=e)
                for i, e in enumerate(dataset_input.add_records(
                    dataset_import.records_to_input(), scale, study.get_grouping_ids()
                ))
                if e is not None
            ]
            await state_store.add_submission_item_errors(event.submission_id, item_errors)
            if item_errors:
                raise ValueError(f"Some items did not parse correctly")

            dataset = await uow.repositories.datasets.create(dataset_input)
            await state_store.set_submission_dataset_id(event.submission_id, dataset.id)
            await uow.commit()
            await state_store.set_submission_status(event.submission_id, SubmissionStatus.COMPLETED)
        except Exception as e:
            await state_store.set_errors(event.submission_id, [f"Failed to create dataset: {type(e).__name__, e}"])
            await state_store.set_submission_status(event.submission_id, SubmissionStatus.FAILED)



@handlers.event_handler()
async def dataset_update_submitted(
        event: events.datasets.DatasetUpdateSubmitted,
        state_store: AbstractStateStore,
        uow_factory: AbstractUnitOfWorkFactory
):
    async with uow_factory.get_uow(user_id=event.agent_id) as uow:
        try:
            await state_store.set_submission_status(event.submission_id, SubmissionStatus.PROCESSING)
            submission = await state_store.get_submission_data(agent_id=event.agent_id, submission_id=event.submission_id)
            dataset_import = DatasetUpdateImport(**submission)
            dataset = await uow.repositories.datasets.get(dataset_id=dataset_import.dataset_id)
            if dataset is None:
                raise ValueError(f"Dataset not found with ID: {dataset_import.dataset_id}")
            else:
                # should we wait till here? we could set this earlier, however
                #  this is the first point at which we guarantee the submitted dataset_id is valid
                await state_store.set_submission_dataset_id(event.submission_id, dataset.id)

            scale = await uow.ontology.get_concept_scale(dataset.concept)

            if dataset_import.study_id is not None and dataset_import.study_id != dataset.study:
                await uow.controls.require_access(ControlledModelLabel.STUDY, [dataset_import.study_id], Access.READ)
                dataset.study = dataset_import.study_id
            contributions = dataset_import.contributions_to_input()
            if contributions is not None:
                await verify_contributions(uow, contributions, stored=dataset.contributions)
                dataset.contributions = contributions_from(contributions)
            # a reference newly cited, by the dataset or its records, may be a file released more widely than the study's
            # licence: checked as the unit of work commits (docs/read-access.md, rule 10)
            if dataset_import.reference_ids is not None:
                cited = set(dataset_import.reference_ids) - set(dataset.references or [])
                await uow.controls.require_read(ControlledModelLabel.REFERENCE, cited)
                uow.controls.defer_licence_check(ControlledModelLabel.REFERENCE, cited)
                dataset.references = dataset_import.reference_ids
            # only the references a record does not already cite need checking
            stored_references = {record.id: set(record.references or []) for record in dataset.records}
            cited = [
                reference_id
                for record in dataset_import.records
                for reference_id in set(record.reference_ids or []) - stored_references.get(record.id, set())
            ]
            await uow.controls.require_read(ControlledModelLabel.REFERENCE, cited)
            uow.controls.defer_licence_check(ControlledModelLabel.REFERENCE, cited)
            # a record moves only to a unit the user can read: another, or one that isn't there, is not found
            stored_units = {record.id: record.unit for record in dataset.records}
            await uow.controls.require_read(ControlledModelLabel.UNIT, [
                record.unit_id for record in dataset_import.records
                if record.unit_id is not None and record.unit_id != stored_units.get(record.id)
            ])

            program = await uow.repositories.programs.get(study_id=dataset.study)
            if program is None:
                raise ValueError(f"Study not found {dataset.study}")
            study = program.get_study(dataset.study)

            item_errors = []
            for i, e in enumerate(dataset.update_records(
                dataset_import.records_to_update(),
                scale,
                study.get_grouping_ids())
            ):
                if e is not None:
                    item_errors.append(ItemError(index=i, error=e))
                    continue
            await state_store.add_submission_item_errors(event.submission_id, item_errors)
            if item_errors:
                raise ValueError(f"Some items did not parse correctly")
            await uow.commit()
            await state_store.set_submission_status(event.submission_id, SubmissionStatus.COMPLETED)
        except Exception as e:
            await state_store.set_errors(event.submission_id, [f"Failed to update dataset: {e}"])
            await state_store.set_submission_status(event.submission_id, SubmissionStatus.FAILED)


@handlers.event_handler()
async def dataset_records_submitted(
        event: events.datasets.DatasetRecordsSubmitted,
        state_store: AbstractStateStore,
        uow_factory: AbstractUnitOfWorkFactory
):
    async with uow_factory.get_uow(user_id=event.agent_id) as uow:
        try:
            await state_store.set_submission_status(event.submission_id, SubmissionStatus.PROCESSING)
            submission = await state_store.get_submission_data(agent_id=event.agent_id, submission_id=event.submission_id)
            records_import = DatasetRecordsImport(**submission)
            # record inputs, as for a new dataset's records: add_records parses them with the dataset's scale
            records = records_import.records_to_input()
            cited = [reference_id for record in records for reference_id in record.references or []]
            await uow.controls.require_read(ControlledModelLabel.REFERENCE, cited)
            # a file they cite may be released more widely than the study's licence: checked as the unit of work commits
            uow.controls.defer_licence_check(ControlledModelLabel.REFERENCE, cited)
            # as for a new dataset, each record is on a unit the user can read
            await uow.controls.require_read(ControlledModelLabel.UNIT, [record.unit for record in records])
            dataset = await uow.repositories.datasets.get(dataset_id=records_import.dataset_id)
            if dataset is None:
                raise ValueError(f"Dataset not found for dataset id: {records_import.dataset_id}")
            else:
                await state_store.set_submission_dataset_id(event.submission_id, dataset.id)

            scale = await uow.ontology.get_concept_scale(dataset.concept)

            program = await uow.repositories.programs.get(study_id=dataset.study)
            if program is None:
                raise ValueError(f"Study not found {dataset.study}")
            study = program.get_study(dataset.study)

            item_errors = []
            for i, e in enumerate(dataset.add_records(records, scale, study.get_grouping_ids())):
                if e is not None:
                    item_errors.append(ItemError(index=i, error=e))
                    continue

            await state_store.add_submission_item_errors(event.submission_id, item_errors)
            if item_errors:
                raise ValueError(f"Some items did not parse correctly")
            await uow.commit()
            await state_store.set_submission_status(event.submission_id, SubmissionStatus.COMPLETED)
        except Exception as e:
            await state_store.set_errors(event.submission_id, [f"Failed to add records to dataset: {type(e).__name__, e}"])
            await state_store.set_submission_status(event.submission_id, SubmissionStatus.FAILED)

