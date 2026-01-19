from ariadne import ObjectType

from src.breedgraph.adapters.redis.state_store import SubmissionStatus

from src.breedgraph.entrypoints.fastapi.graphql.decorators import graphql_payload, require_authentication

from src.breedgraph.domain.model.datasets import DatasetInput, DatasetStored, DatasetOutput, DataRecordStored
from src.breedgraph.domain.model.errors import ItemError
from src.breedgraph.service_layer.handlers.commands.regions import update_location
from src.breedgraph.service_layer.queries.read_models import DatasetSummary

from src.breedgraph.entrypoints.fastapi.graphql.resolvers.queries.context_loaders import (
    update_ontology_map,
    update_units_map,
    update_locations_map
)

from typing import List

import logging
logger = logging.getLogger(__name__)

from . import graphql_query
from ..registry import graphql_resolvers
dataset = ObjectType("Dataset")
record = ObjectType("Record")
dataset_submission = ObjectType("DatasetSubmission")
dataset_summary = ObjectType("DatasetSummary")

graphql_resolvers.register_type_resolvers(dataset, record, dataset_submission, dataset_summary)

"""Datasets resolver"""
@graphql_query.field("datasets")
@graphql_payload
@require_authentication
async def get_datasets(_, info, dataset_id: int = None, concept_id: int = None) -> List[DatasetOutput]:
    user_id = info.context.get('user_id')
    bus = info.context.get('bus')
    async with bus.uow.get_uow(user_id=user_id) as uow:
        if dataset is None:
            return [d.to_output() async for d in uow.repositories.datasets.get_all(concept_id=concept_id)]
        else:
            d = await uow.repositories.datasets.get(dataset_id=dataset_id)
            if d is not None:
                return [d.to_output()]
            else:
                return []


@dataset.field('concept')
async def resolve_concept(obj, info):
    await update_ontology_map(info.context, entry_ids=[obj.concept])
    ontology_map = info.context.get('ontology_map')
    return ontology_map.get(obj.concept)


@record.field('unit')
async def resolve_unit(obj, info):
    await update_units_map(info.context, unit_ids=[obj.unit])
    units_map = info.context.get('units_map')
    return units_map.get(obj.unit)


"""Submission resolver"""
@graphql_query.field("datasetsSubmission")
@graphql_payload
@require_authentication
async def get_submission(_, info, submission_id: str) :
    return submission_id

@dataset_submission.field("data")
async def resolve_submission_data(submission_id: str, info):
    logger.debug(f"Resolving submission data for submission_id: {submission_id}")
    user_id = info.context.get('user_id')
    bus = info.context.get('bus')
    return await bus.state_store.get_submission_data(agent_id=user_id, submission_id=submission_id)

@dataset_submission.field("datasetId")
async def resolve_submission_dataset_id(submission_id: str, info) -> str:
    user_id = info.context.get('user_id')
    bus = info.context.get('bus')
    logger.debug(f"Resolving submission dataset_id for submission_id: {submission_id}")
    dataset_id = await bus.state_store.get_submission_dataset_id(agent_id=user_id, submission_id=submission_id)
    return dataset_id

@dataset_submission.field("status")
async def resolve_submission_status(submission_id: str, info) -> SubmissionStatus:
    user_id = info.context.get('user_id')
    bus = info.context.get('bus')
    logger.debug(f"Resolving submission status for submission_id: {submission_id}")
    status = await bus.state_store.get_submission_status(agent_id=user_id, submission_id=submission_id)
    return status

@dataset_submission.field("errors")
async def resolve_submission_errors(submission_id: str, info) -> List[str]:
    user_id = info.context.get('user_id')
    bus = info.context.get('bus')
    logger.debug(f"Resolving submission errors for submission_id: {submission_id}")
    errors = await bus.state_store.get_submission_errors(agent_id=user_id, submission_id=submission_id)
    logger.debug(f'errors resolved: {errors}')
    return errors


@dataset_submission.field("itemErrors")
async def resolve_submission_item_errors(submission_id: str, info) -> List[ItemError]:
    user_id = info.context.get('user_id')
    bus = info.context.get('bus')
    logger.debug(f"Resolving submission item errors for submission_id: {submission_id}")
    errors = await bus.state_store.get_submission_item_errors(agent_id=user_id, submission_id=submission_id)
    return errors

"""Summary resolvers"""
@graphql_query.field("datasetsSummaries")
@graphql_payload
@require_authentication
async def get_dataset_summaries(_, info, study_id: int = None) -> List[DatasetSummary]:
    user_id = info.context.get('user_id')
    bus = info.context.get('bus')
    async with bus.uow.get_views(user_id=user_id) as views:
        summaries = await views.datasets.get_dataset_summaries(study_id=study_id)
        return summaries

@dataset_summary.field("concept")
async def resolve_summary_concept(obj, info):
    await update_ontology_map(info.context, entry_ids=[obj.concept_id])
    ontology_map = info.context.get('ontology_map')
    return ontology_map.get(obj.concept)

@dataset_summary.field("subjects")
async def resolve_summary_subjects(obj, info):
    await update_ontology_map(info.context, entry_ids=[obj.subject_ids])
    ontology_map = info.context.get('ontology_map')
    return [ontology_map.get(subject_id) for subject_id in obj.subject_ids]

@dataset_summary.field("locations")
async def resolve_summary_locations(obj, info):
    await update_locations_map(info.context, location_ids=obj.location_ids)
    locations_map = info.context.get('locations_map')
    return [locations_map.get(location_id) for location_id in obj.location_ids]

@dataset_summary.field("blocks")
async def resolve_summary_blocks(obj, info):
    await update_units_map(info.context, unit_ids=obj.block_ids)
    locations_map = info.context.get('locations_map')
    return [locations_map.get(location_id) for location_id in obj.location_ids]