import logging

from breedgraph.domain.model import ScaleCategoryStored

logger = logging.getLogger(__name__)

from ..registry import handlers

from breedgraph.service_layer.infrastructure import AbstractStateStore, AbstractUnitOfWorkFactory
from breedgraph.service_layer.application import OntologyApplicationService

from breedgraph.domain import events
from breedgraph.domain.model.submissions import SubmissionStatus
from breedgraph.domain.model.ontology import OntologyEntryLabel, ScaleStored, ScaleType
from breedgraph.domain.model.errors import ItemError

from breedgraph.domain.importers import DatasetImport, DatasetUpdateImport, RecordImport

async def get_scale_and_categories(concept_id, ontology_service: OntologyApplicationService) -> tuple[ScaleStored, list[ScaleCategoryStored]]:
    scale_id = await ontology_service.get_scale_id(entry_id=concept_id)
    scale: ScaleStored = await ontology_service.get_entry(scale_id, label=OntologyEntryLabel.SCALE)
    if scale.scale_type in [ScaleType.ORDINAL, ScaleType.NOMINAL]:
        category_ids = await ontology_service.get_scale_category_ids(scale.id)
        categories = [await ontology_service.get_entry(c) for c in category_ids]
        for category in categories:
            if not isinstance(category, ScaleCategoryStored):
                raise ValueError("Supplied ontology entry ID for category is not a ScaleCategory")
    else:
        categories = None
    return scale, categories


@handlers.event_handler()
async def dataset_submitted(
        event: events.datasets.DatasetSubmitted,
        state_store: AbstractStateStore,
        uow_factory: AbstractUnitOfWorkFactory
):
    async with uow_factory.get_uow(user_id=event.agent_id, write_team=event.write_team, release=event.release) as uow:
        try:
            await state_store.set_submission_status(event.submission_id, SubmissionStatus.PROCESSING)
            submission = await state_store.get_submission_data(agent_id=event.agent_id, submission_id=event.submission_id)
            dataset_import = DatasetImport(**submission)
            scale, categories = await get_scale_and_categories(
                concept_id=dataset_import.concept_id,
                ontology_service=uow.ontology
            )
            dataset = await uow.repositories.datasets.create(dataset_import.to_input_for_create())
            item_errors = []

            if dataset_import.records:
                for i, e in enumerate(dataset.add_records(dataset_import.dump_records(), scale, categories)):
                    if e is not None:
                        item_errors.append(ItemError(index=i, error=e))
                        continue

            await state_store.set_submission_dataset_id(event.submission_id, dataset.id)
            await state_store.add_submission_item_errors(event.submission_id, item_errors)
            if item_errors:
                raise ValueError(f"Some items did not parse correctly")
            await uow.commit()
            await state_store.set_submission_status(event.submission_id, SubmissionStatus.COMPLETED)
        except Exception as e:
            await state_store.add_submission_errors(event.submission_id, [f"Failed to create dataset: {type(e).__name__, e}"])
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

            scale, categories = await get_scale_and_categories(dataset.concept, uow.ontology)

            if dataset_import.study_id is not None:
                dataset.study = dataset_import.study_id
            if dataset_import.contributor_ids is not None:
                dataset.contributors = dataset_import.contributor_ids
            if dataset_import.reference_ids is not None:
                dataset.references = dataset_import.reference_ids

            item_errors = []
            for i, e in enumerate(dataset.update_records(dataset_import.dump_records(), scale, categories)):
                if e is not None:
                    item_errors.append(ItemError(index=i, error=e))
                    continue
            await state_store.add_submission_item_errors(event.submission_id, item_errors)
            if item_errors:
                raise ValueError(f"Some items did not parse correctly")
            await uow.commit()
            await state_store.set_submission_status(event.submission_id, SubmissionStatus.COMPLETED)
        except Exception as e:
            await state_store.add_submission_errors(event.submission_id, [f"Failed to update dataset: {e}"])
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
            dataset_id = submission.get("dataset_id")
            records = [RecordImport(**r).model_dump() for r in submission.get("records", [])]
            dataset = await uow.repositories.datasets.get(dataset_id=dataset_id)
            if dataset is None:
                raise ValueError(f"Dataset not found for dataset id: {dataset_id}")
            else:
                await state_store.set_submission_dataset_id(event.submission_id, dataset.id)

            scale, categories = await get_scale_and_categories(
                concept_id=dataset.concept,
                ontology_service=uow.ontology
            )
            item_errors = []

            for i, e in enumerate(dataset.add_records(records, scale, categories)):
                if e is not None:
                    item_errors.append(ItemError(index=i, error=e))
                    continue

            await state_store.add_submission_item_errors(event.submission_id, item_errors)
            if item_errors:
                raise ValueError(f"Some items did not parse correctly")
            await uow.commit()
            await state_store.set_submission_status(event.submission_id, SubmissionStatus.COMPLETED)
        except Exception as e:
            await state_store.add_submission_errors(event.submission_id, [f"Failed to add records to dataset: {type(e).__name__, e}"])
            await state_store.set_submission_status(event.submission_id, SubmissionStatus.FAILED)

