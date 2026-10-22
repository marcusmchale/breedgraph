from numpy import datetime64
from ariadne import ObjectType
from graphql import FragmentSpreadNode, InlineFragmentNode

from breedgraph.adapters.redis.state_store import SubmissionStatus

from breedgraph.entrypoints.fastapi.graphql.decorators import graphql_payload, require_authentication

from breedgraph.domain.model.contributions import Contribution
from breedgraph.domain.model.datasets import DatasetInput, DatasetStored, DatasetOutput, DataRecordStored
from breedgraph.domain.model.errors import ItemError
from breedgraph.service_layer.handlers.commands.location_trees import update_location
from breedgraph.service_layer.queries.read_models import DatasetSummary, OntologyViewMode

from breedgraph.entrypoints.fastapi.graphql.resolvers.queries.context_loaders import (
    update_ontology_map,
    update_units_map,
    update_unit_names_map,
    get_context_views,
    get_context_lock,
    update_germplasm_map,
    update_locations_map,
    update_layouts_map,
    update_reference_map
)

from typing import List

import logging
logger = logging.getLogger(__name__)

from breedgraph.entrypoints.fastapi.graphql.licences import require_licence_accepted
from . import graphql_query
from ..registry import graphql_resolvers
dataset = ObjectType("Dataset")
record = ObjectType("Record")
dataset_submission = ObjectType("DatasetSubmission")
dataset_summary = ObjectType("DatasetSummary")
datasets_unit = ObjectType("DatasetsUnit")
submitted_data = ObjectType("SubmittedData")
dataset_place = ObjectType("DatasetPlace")
dataset_place_layout = ObjectType("DatasetPlaceLayout")

graphql_resolvers.register_type_resolvers(
    dataset, record, dataset_submission, dataset_summary, datasets_unit, submitted_data, dataset_place, dataset_place_layout
)

"""Datasets resolver"""
@graphql_query.field("datasets")
@graphql_payload
async def get_datasets(
        _,
        info,
        ids: List[int]|None = None,
        study_ids: List[int]|None = None,
        concept_ids: List[int]|None = None
) -> List[DatasetOutput]:
    # Read through the datasets view: no aggregate, tracking or controller lookups for a read
    async with get_context_lock(info.context):
        views = await get_context_views(info.context)
        return await views.datasets.get_datasets(dataset_ids=ids, study_ids=study_ids, concept_ids=concept_ids)

async def _readable_dataset_ids(views, dataset_ids: List[int]) -> List[int]:
    """The given datasets the user can read; the others contribute no units or records"""
    if not dataset_ids:
        return []
    datasets = await views.datasets.get_datasets(dataset_ids=[int(dataset_id) for dataset_id in dataset_ids])
    return [dataset.id for dataset in datasets if not dataset.redacted]

@graphql_query.field("datasetsUnits")
@graphql_payload
async def get_datasets_units(_, info, dataset_ids: List[int], parent_ids: List[int]|None = None, start=None, end=None):
    async with get_context_lock(info.context):
        views = await get_context_views(info.context)
        readable_ids = await _readable_dataset_ids(views, dataset_ids)
        if not readable_ids:
            return []
        level = await views.datasets.get_unit_level(
            dataset_ids=readable_ids,
            parent_ids=[int(parent_id) for parent_id in parent_ids] if parent_ids is not None else None,
            start=start, end=end
        )
    # Preload the level's units in one call, instead of one per node
    await update_units_map(info.context, unit_ids=[node.id for node in level])
    return level

@datasets_unit.field("unit")
def resolve_datasets_unit_unit(obj, info):
    return info.context.get('units_map', {}).get(obj.id)

@graphql_query.field("datasetsUnitsBySubject")
@graphql_payload
async def get_datasets_units_by_subject(_, info, dataset_ids: List[int], unit_ids: List[int]|None = None, start=None, end=None):
    async with get_context_lock(info.context):
        views = await get_context_views(info.context)
        readable_ids = await _readable_dataset_ids(views, dataset_ids)
        if not readable_ids:
            return []
        by_subject = await views.datasets.get_units_by_subject(
            dataset_ids=readable_ids,
            unit_ids=[int(unit_id) for unit_id in unit_ids] if unit_ids is not None else None,
            start=start, end=end
        )
    return [{'subject': subject, 'units': units} for subject, units in by_subject.items()]

@graphql_query.field("datasetsPlaces")
@graphql_payload
async def get_datasets_places(_, info, dataset_ids: List[int], location_type_ids: List[int]):
    async with get_context_lock(info.context):
        views = await get_context_views(info.context)
        readable_ids = await _readable_dataset_ids(views, dataset_ids)
        if not readable_ids:
            return []
        return await views.datasets.get_places(
            dataset_ids=readable_ids, location_type_ids=[int(type_id) for type_id in location_type_ids]
        )

@dataset_place.field('location')
async def resolve_place_location(obj, info):
    await update_locations_map(info.context, location_ids=[obj.location_id])
    return info.context.get('locations_map').get(obj.location_id)

@dataset_place_layout.field('layout')
async def resolve_place_layout(obj, info):
    await update_layouts_map(info.context, layout_ids=[obj.layout_id])
    return info.context.get('layouts_map').get(obj.layout_id)

@dataset.field('studyId')
def resolve_study_id(obj, info):
    return obj.study

@dataset.field('concept')
async def resolve_concept(obj, info):
    await update_ontology_map(info.context, entry_ids=[obj.concept], view=OntologyViewMode.REFERENTIAL)
    ontology_map = info.context.get('ontology_map')
    return ontology_map.get(obj.concept)

@dataset.field('records')
async def resolve_records(obj, info, unit_ids=None, start=None, end=None, offset=None, limit=None, include_below=None):
    """
    A page of the dataset's records, read through the datasets view; nothing for a dataset the user cannot read, and
    refused without its licence accepted where the user must accept it
    """
    if obj.redacted:
        return []
    await require_licence_accepted(info.context, obj)
    async with get_context_lock(info.context):
        views = await get_context_views(info.context)
        records = await views.datasets.get_records(
            dataset_id=obj.id,
            unit_ids=[int(unit_id) for unit_id in unit_ids] if unit_ids is not None else None,
            start=start, end=end, offset=offset or 0, limit=limit, include_below=include_below is not False
        )
    # Preload what the record resolvers need in one call per page, instead of one per record
    await update_unit_names_map(info.context, unit_ids=[record.get('unit') for record in records])
    names_map = info.context.get('unit_names_map', {})
    await update_germplasm_map(
        info.context,
        entry_ids=[names_map[record['unit']].germplasm for record in records if record.get('unit') in names_map]
    )
    await update_reference_map(
        info.context,
        reference_ids=[reference_id for record in records for reference_id in (record.get('references') or [])]
    )
    return records

@dataset.field('unitIds')
async def resolve_unit_ids(obj, info, unit_ids=None, start=None, end=None):
    # the units with records under the same narrowing as records, so a client can page by unit; nothing if unreadable
    if obj.redacted:
        return []
    async with get_context_lock(info.context):
        views = await get_context_views(info.context)
        return await views.datasets.get_unit_ids(
            dataset_id=obj.id,
            unit_ids=[int(unit_id) for unit_id in unit_ids] if unit_ids is not None else None,
            start=start, end=end
        )

@dataset.field('recordCount')
async def resolve_record_count(obj, info, unit_ids=None, start=None, end=None):
    # as with the records themselves, nothing for a dataset the user cannot read
    if obj.redacted:
        return 0
    # the header carries the full count; a narrowed count is read when the records' filters are given
    if unit_ids is None and start is None and end is None:
        return obj.record_count
    async with get_context_lock(info.context):
        views = await get_context_views(info.context)
        return await views.datasets.count_records(
            dataset_id=obj.id,
            unit_ids=[int(unit_id) for unit_id in unit_ids] if unit_ids is not None else None,
            start=start, end=end
        )

@dataset.field('licence')
async def resolve_licence(obj, info):
    """The licence of the dataset's study, readable wherever the dataset is by release (docs/read-access.md rule 10)"""
    if obj.redacted or obj.licence is None:
        return None
    await update_reference_map(info.context, reference_ids=[obj.licence])
    return info.context['reference_map'].get(obj.licence)

@dataset.field('licenceRequired')
def resolve_licence_required(obj, info) -> bool:
    return obj.licence_required

@dataset.field('dimensions')
async def resolve_dimensions(obj, info):
    # what the records span, read without them, its values included; nothing for a dataset the user cannot read, and
    # refused without its licence accepted, as the records are
    if obj.redacted:
        return None
    await require_licence_accepted(info.context, obj)
    async with get_context_lock(info.context):
        views = await get_context_views(info.context)
        return await views.datasets.get_dimensions(dataset_id=obj.id)

# The record resolvers answer synchronously from what resolve_records preloaded, and return an awaitable only when
# something is missing: an async resolver costs an asyncio task per record, which dominates a page of 25,000 records

@record.field('unit')
def resolve_unit(obj: dict, info):
    # Records credit units by id, name and germplasm; the names map is filled when the records are resolved
    unit_id = obj.get('unit')
    names_map = info.context.get('unit_names_map', {})
    if unit_id in names_map:
        return names_map[unit_id]
    return _load_unit(info, unit_id)

async def _load_unit(info, unit_id):
    await update_units_map(info.context, unit_ids=[unit_id])
    return info.context.get('units_map', {}).get(unit_id)

@record.field('references')
def resolve_references(obj: dict, info):
    reference_ids = obj.get('references')
    reference_map = info.context.get('reference_map', {})
    if all(ref_id in reference_map for ref_id in reference_ids):
        return [reference_map.get(ref_id) for ref_id in reference_ids]
    return _load_references(info, reference_ids)

async def _load_references(info, reference_ids):
    await update_reference_map(info.context, reference_ids=reference_ids)
    reference_map = info.context.get('reference_map')
    return [reference_map.get(ref_id) for ref_id in reference_ids]


"""Submission resolver"""
@graphql_query.field("datasetsSubmission")
@graphql_payload
@require_authentication
async def get_submission(_, info, id: str) :
    return id

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
    status = await bus.state_store.get_status(agent_id=user_id, key=submission_id)
    return status

@dataset_submission.field("errors")
async def resolve_submission_errors(submission_id: str, info) -> List[str]:
    user_id = info.context.get('user_id')
    bus = info.context.get('bus')
    logger.debug(f"Resolving submission errors for submission_id: {submission_id}")
    errors = await bus.state_store.get_errors(agent_id=user_id, key=submission_id)
    logger.debug(f'errors raised during dataset submission: {errors}')
    return errors

@dataset_submission.field("itemErrors")
async def resolve_submission_item_errors(submission_id: str, info) -> List[ItemError]:
    user_id = info.context.get('user_id')
    bus = info.context.get('bus')
    logger.debug(f"Resolving submission item errors for submission_id: {submission_id}")
    errors = await bus.state_store.get_submission_item_errors(agent_id=user_id, submission_id=submission_id)
    return errors

"""Summary resolvers"""
# The read model fields each DatasetSummary field needs, so the summaries read only what was asked for
SUMMARY_FIELDS_BY_GRAPHQL_FIELD = {
    'subjects': 'subject_ids',
    'locations': 'location_ids',
    'unitRoots': 'unit_root_ids',
    'unit_count': 'unit_count',
    'record_count': 'record_count',
    'start': 'start',
    'end': 'end'
}

def selected_field_names(info, path: List[str]) -> set[str]:
    """The names of the fields selected below the resolved field along a path of field names, through fragments"""
    def children(selection_set):
        for selection in selection_set.selections if selection_set else []:
            if isinstance(selection, FragmentSpreadNode):
                yield from children(info.fragments[selection.name.value].selection_set)
            elif isinstance(selection, InlineFragmentNode):
                yield from children(selection.selection_set)
            else:
                yield selection

    nodes = list(info.field_nodes)
    for name in path:
        nodes = [child for node in nodes for child in children(node.selection_set) if child.name.value == name]
    return {child.name.value for node in nodes for child in children(node.selection_set)}

@graphql_query.field("datasetsSummaries")
@graphql_payload
async def get_dataset_summaries(_, info, study_id: int|None = None) -> List[DatasetSummary]:
    user_id = info.context.get('user_id')
    bus = info.context.get('bus')
    selected = selected_field_names(info, ['result'])
    fields = {SUMMARY_FIELDS_BY_GRAPHQL_FIELD[name] for name in selected if name in SUMMARY_FIELDS_BY_GRAPHQL_FIELD}
    async with bus.views_factory.get_views(user_id=user_id) as views:
        summaries = await views.datasets.get_dataset_summaries(study_id=study_id, fields=fields)
    # Preload what the summaries refer to in one call each, instead of one per summary
    await update_ontology_map(
        info.context,
        entry_ids=[summary.concept_id for summary in summaries] + [
            subject_id for summary in summaries for subject_id in summary.subject_ids
        ],
        view=OntologyViewMode.REFERENTIAL
    )
    if 'unit_root_ids' in fields:
        await update_units_map(info.context, unit_ids=[unit_root_id for summary in summaries for unit_root_id in summary.unit_root_ids])
    if 'location_ids' in fields:
        await update_locations_map(info.context, location_ids={
            location_id for summary in summaries for location_id in summary.location_ids
        })
    return summaries

@dataset_summary.field("concept")
async def resolve_summary_concept(obj, info):
    await update_ontology_map(info.context, entry_ids=[obj.concept_id], view=OntologyViewMode.REFERENTIAL)
    ontology_map = info.context.get('ontology_map')
    return ontology_map.get(obj.concept_id)

@dataset_summary.field("subjects")
async def resolve_summary_subjects(obj, info):
    await update_ontology_map(info.context, entry_ids=obj.subject_ids, view=OntologyViewMode.REFERENTIAL)
    ontology_map = info.context.get('ontology_map')
    return [ontology_map.get(subject_id) for subject_id in obj.subject_ids]

@dataset_summary.field("locations")
async def resolve_summary_locations(obj, info):
    await update_locations_map(info.context, location_ids=obj.location_ids)
    locations_map = info.context.get('locations_map')
    return [locations_map.get(location_id) for location_id in obj.location_ids]

@dataset_summary.field("unitRoots")
async def resolve_summary_unit_graphs(obj, info):
    await update_units_map(info.context, unit_ids=obj.unit_root_ids)
    units_map = info.context.get('units_map')
    return [units_map.get(unit_id) for unit_id in obj.unit_root_ids]


@dataset.field("references")
async def resolve_dataset_references(obj, info):
    await update_reference_map(info.context, reference_ids=obj.references)
    reference_map = info.context.get('reference_map')
    return [reference_map.get(reference_id) for reference_id in obj.references]

@submitted_data.field("contributions")
async def resolve_submitted_contributions(obj: dict, info):
    return [
        Contribution(person=contribution['person_id'], roles=list(contribution.get('role_ids') or []))
        for contribution in obj.get('contributions') or []
    ]
