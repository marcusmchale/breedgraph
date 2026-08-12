from ariadne import ObjectType
from breedgraph.domain.model.germplasm import (
    GermplasmStored, GermplasmOutput, GermplasmRelationship
)
from breedgraph.entrypoints.fastapi.graphql.decorators import graphql_payload, require_authentication
from breedgraph.entrypoints.fastapi.graphql.resolvers.queries.context_loaders import (
    update_germplasm_map, update_locations_map, update_ontology_map, update_reference_map
)

from typing import List

import logging

from breedgraph.service_layer.queries.read_models import OntologyViewMode

logger = logging.getLogger(__name__)

from . import graphql_query
from ..registry import graphql_resolvers

germplasm_entry = ObjectType("GermplasmEntry")
germplasm_relationship = ObjectType("GermplasmRelationship")

graphql_resolvers.register_type_resolvers(germplasm_entry, germplasm_relationship)

@graphql_query.field("germplasmEntries")
@graphql_payload
@require_authentication
async def get_germplasm_entries(
        _,
        info,
        ids: List[int]|None = None,
        names: List[str]|None = None,
) -> List[GermplasmOutput]:
    await update_germplasm_map(info.context, entry_ids=ids, names=names)
    germplasm = [value for key, value in info.context.get('germplasm_map').items()]
    return germplasm

@graphql_query.field("germplasmCrops")
@graphql_payload
@require_authentication
async def get_germplasm_crops(
        _,
        info
) -> List[GermplasmOutput]:
    bus = info.context.get('bus')
    user_id = info.context.get('user_id')
    async with bus.uow_factory.get_uow(user_id=user_id) as uow:
        return [entry async for entry in uow.germplasm.get_root_entries(as_output=True)]

async def resolve_germplasm_entries(context, entry_ids):
    await update_germplasm_map(context, entry_ids=entry_ids)
    germplasm_map = context.get('germplasm_map')
    return [germplasm_map[entry_id] for entry_id in entry_ids]


@germplasm_entry.field("controlMethods")
async def resolve_germplasm_control_methods(obj: GermplasmStored, info):
    if not obj.control_methods:
        return None
    await update_ontology_map(info.context, entry_ids=obj.control_methods, view=OntologyViewMode.REFERENTIAL)
    ontology_map = info.context.get('ontology_map')
    return [ontology_map[i] for i in obj.control_methods]

@germplasm_entry.field("origin")
async def resolve_germplasm_location(obj: GermplasmStored, info):
    if obj.origin is None:
        return None
    await update_locations_map(info.context, location_ids=[obj.origin])
    locations_map = info.context.get('locations_map')
    return locations_map[obj.origin]

@germplasm_entry.field("references")
async def resolve_germplasm_references(obj: GermplasmStored, info):
    if not obj.references:
        return None
    await update_reference_map(info.context, reference_ids=obj.references)
    reference_map = info.context.get('reference_map')
    return [reference_map[i] for i in obj.references]

@germplasm_relationship.field("source")
async def resolve_source_entry(obj, info):
    await update_germplasm_map(info.context, entry_ids=[obj.source_id])
    logger.debug(f'updated with {obj.source_id}')
    germplasm_map = info.context.get('germplasm_map')
    return germplasm_map[obj.source_id]

@germplasm_relationship.field("sink")
async def resolve_sink_entry(obj, info):
    await update_germplasm_map(info.context, entry_ids=[obj.sink_id])
    germplasm_map = info.context.get('germplasm_map')
    return germplasm_map[obj.sink_id]