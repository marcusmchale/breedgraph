import logging


logger = logging.getLogger(__name__)

from ..registry import handlers

from breedgraph.service_layer.infrastructure import AbstractStateStore, AbstractUnitOfWorkFactory
from breedgraph.service_layer.application import OntologyApplicationService

from breedgraph.domain import events
from breedgraph.domain.model.datasets import DatasetInput, DatasetStored, DataRecordInput
from breedgraph.domain.model.submissions import SubmissionStatus
from breedgraph.domain.model.ontology import OntologyEntryLabel, ScaleStored, ScaleType

from breedgraph.domain.model.errors import ItemError

async def get_scale_and_categories(concept_id, ontology_service: OntologyApplicationService):
    scale_id = await ontology_service.get_scale_id(entry_id=concept_id)
    scale: ScaleStored = await ontology_service.get_entry(scale_id, label=OntologyEntryLabel.SCALE)
    if scale.scale_type in [ScaleType.ORDINAL, ScaleType.NOMINAL]:
        category_ids = await ontology_service.get_scale_category_ids(scale.id)
        categories = [await ontology_service.get_entry(c) for c in category_ids]
    else:
        categories = None
    return scale, categories


@handlers.event_handler()
async def records_submitted(
        event: events.datasets.RecordsSubmitted,
        state_store: AbstractStateStore,
        uow_factory: AbstractUnitOfWorkFactory
):
    async with uow_factory.get_uow(user_id=event.agent_id) as uow:
        try:
            await state_store.set_submission_status(event.submission_id, SubmissionStatus.PROCESSING)
            submission = await state_store.get_submission_data(agent_id=event.agent_id, submission_id=event.submission_id)
            scale, categories = await get_scale_and_categories(submission.get("concept_id"), uow.ontology)
            records = submission.pop('records')
            dataset = await uow.repositories.datasets.create(DatasetInput(**submission))
            item_errors = []
            if records:
                for i, e in enumerate(dataset.add_records(records, scale, categories)):
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
async def record_updates_submitted(
        event: events.datasets.RecordUpdatesSubmitted,
        state_store: AbstractStateStore,
        uow_factory: AbstractUnitOfWorkFactory
):
    async with uow_factory.get_uow(user_id=event.agent_id) as uow:
        try:
            await state_store.set_submission_status(event.submission_id, SubmissionStatus.PROCESSING)
            submission = await state_store.get_submission_data(agent_id=event.agent_id, submission_id=event.submission_id)
            dataset = await uow.repositories.datasets.get(dataset_id=submission.get("dataset_id"))
            scale, categories = await get_scale_and_categories(dataset.concept, uow.ontology)
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
            await state_store.add_submission_item_errors(event.submission_id, item_errors)
            if item_errors:
                raise ValueError(f"Some items did not parse correctly")
            await uow.commit()
            await state_store.set_submission_status(event.submission_id, SubmissionStatus.COMPLETED)
        except Exception as e:
            await state_store.add_submission_errors(event.submission_id, [f"Failed to update dataset: {e}"])
            await state_store.set_submission_status(event.submission_id, SubmissionStatus.FAILED)
