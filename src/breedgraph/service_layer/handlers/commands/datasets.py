
from src.breedgraph.service_layer.infrastructure import AbstractUnitOfWorkFactory

from src.breedgraph.service_layer.infrastructure import AbstractStateStore
from src.breedgraph.service_layer.application import OntologyApplicationService

from src.breedgraph.domain import commands
from src.breedgraph.domain.model.datasets import DatasetInput, DatasetStored, DataRecordInput
from src.breedgraph.domain.model.ontology import OntologyEntryLabel, ScaleStored, ScaleType
from src.breedgraph.domain.model.errors import ItemError
from src.breedgraph.domain.model.submissions import SubmissionStatus

from ..registry import handlers

import logging
logger = logging.getLogger(__name__)

@handlers.command_handler()
async def create_dataset(
        cmd: commands.datasets.CreateDataset,
        uow: AbstractUnitOfWorkFactory,
        state_store: AbstractStateStore
):
    async with uow.get_uow(user_id=cmd.agent_id) as uow:
        try:
            await state_store.set_submission_status(cmd.submission_id, SubmissionStatus.PROCESSING)
            submission = await state_store.get_submission_data(agent_id=cmd.agent_id, submission_id=cmd.submission_id)
            scale, categories = await get_scale_and_categories(uow, submission.get("concept_id"))
            dataset = await uow.repositories.datasets.create(DatasetInput(concept=submission.get("concept_id")))
            item_errors = []
            records = submission.get('records')
            if records:
                for i, e in enumerate(dataset.add_records(records, scale, categories)):
                    if e is not None:
                        item_errors.append(ItemError(index=i, error=e))
                        continue
            await state_store.set_submission_dataset_id(cmd.submission_id, dataset.id)
            await state_store.add_submission_item_errors(cmd.submission_id, item_errors)
            if item_errors:
                raise ValueError(f"Some items did not parse correctly")
            await uow.commit()
            await state_store.set_submission_status(cmd.submission_id, SubmissionStatus.COMPLETED)
        except Exception as e:
            await state_store.add_submission_errors(cmd.submission_id, [f"Failed to create dataset: {e}"])
            await state_store.set_submission_status(cmd.submission_id, SubmissionStatus.FAILED)

@handlers.command_handler()
async def update_dataset(
        cmd: commands.datasets.UpdateDataset,
        uow: AbstractUnitOfWorkFactory,
        state_store: AbstractStateStore
):
    async with uow.get_uow(user_id=cmd.agent_id) as uow:
        try:
            await state_store.set_submission_status(cmd.submission_id, SubmissionStatus.PROCESSING)
            submission = await state_store.get_submission_data(agent_id=cmd.agent_id, submission_id=cmd.submission_id)
            scale, categories = await get_scale_and_categories(uow, submission.get("concept_id"))
            dataset = await uow.repositories.datasets.get(dataset_id=submission.get("dataset_id"))

            concept_id = submission.get('concept_id')
            if concept_id:
                dataset.concept = concept_id
            study_id = submission.get('study_id')
            if study_id:
                dataset.study = study_id
            contributor_ids = submission.get('contributor_ids')
            if contributor_ids:
                dataset.contributors = contributor_ids
            reference_ids = submission.get('reference_ids')
            if reference_ids:
                dataset.references = reference_ids

            item_errors = []
            for i, e in enumerate(dataset.update_records(submission.get('records'), scale, categories)):
                if e is not None:
                    item_errors.append(ItemError(index=i, error=e))
                    continue

            await state_store.add_submission_item_errors(cmd.submission_id, item_errors)
            if item_errors:
                raise ValueError(f"Some items did not parse correctly")
            await uow.commit()
            await state_store.set_submission_status(cmd.submission_id, SubmissionStatus.COMPLETED)
        except Exception as e:
            await state_store.add_submission_errors(cmd.submission_id, [f"Failed to update dataset: {e}"])
            await state_store.set_submission_status(cmd.submission_id, SubmissionStatus.FAILED)


@handlers.command_handler()
async def add_records(
        cmd: commands.datasets.AddRecords,
        uow: AbstractUnitOfWorkFactory,
        state_store: AbstractStateStore
):
    async with uow.get_uow(user_id=cmd.agent_id) as uow:
        try:
            await state_store.set_submission_status(cmd.submission_id, SubmissionStatus.PROCESSING)
            submission = await state_store.get_submission_data(agent_id=cmd.agent_id, submission_id=cmd.submission_id)
            scale, categories = await get_scale_and_categories(uow, submission.get("concept_id"))
            dataset = await uow.repositories.datasets.get(dataset_id=submission.get("dataset_id"))

            item_errors = []
            for i, e in enumerate(dataset.add_records(submission.get('records'), scale, categories)):
                if e is not None:
                    item_errors.append(ItemError(index=i, error=e))
                    continue

            await state_store.add_submission_item_errors(cmd.submission_id, item_errors)
            if item_errors:
                raise ValueError(f"Some items did not parse correctly")
            await uow.commit()
            await state_store.set_submission_status(cmd.submission_id, SubmissionStatus.COMPLETED)
        except Exception as e:
            await state_store.add_submission_errors(cmd.submission_id, [f"Failed to create dataset: {e}"])
            await state_store.set_submission_status(cmd.submission_id, SubmissionStatus.FAILED)


@handlers.command_handler()
async def remove_records(
        cmd: commands.datasets.RemoveRecords,
        uow: AbstractUnitOfWorkFactory
):
    async with uow.get_uow(user_id=cmd.agent_id) as uow:
        dataset = await uow.repositories.datasets.get(dataset_id=cmd.dataset_id)
        item_errors = []
        for i, e in enumerate(dataset.remove_records(cmd.record_ids)):
            if e is not None:
                item_errors.append(ItemError(index=i, error=e))
                continue

        if item_errors:
            raise ValueError(f"Failed to remove some records: {item_errors}")

        await uow.commit()


async def get_scale_and_categories(uow, concept_id):
    ontology_service: OntologyApplicationService = uow.ontology
    scale_id = await ontology_service.get_scale_id(entry_id=concept_id)
    scale: ScaleStored = await ontology_service.get_entry(scale_id, label=OntologyEntryLabel.SCALE)
    if scale.scale_type in [ScaleType.ORDINAL, ScaleType.NOMINAL]:
        category_ids = await ontology_service.get_scale_category_ids(scale.id)
        categories = [await ontology_service.get_entry(c) for c in category_ids]
    else:
        categories = None
    return scale, categories
