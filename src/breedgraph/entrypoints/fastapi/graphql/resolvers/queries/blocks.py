from ariadne import ObjectType


from src.breedgraph.entrypoints.fastapi.graphql.decorators import graphql_payload, require_authentication
from src.breedgraph.entrypoints.fastapi.graphql.resolvers.queries.context_loaders import (
    update_units_map,
    update_ontology_map,
    update_locations_map,
    update_layouts_map,
    update_germplasm_map
)

from src.breedgraph.domain.model.blocks import UnitOutput, Position

from typing import List

import logging
logger = logging.getLogger(__name__)

from . import graphql_query
from ..registry import graphql_resolvers
unit = ObjectType("Unit")
position = ObjectType("Position")
graphql_resolvers.register_type_resolvers(unit, position)

@graphql_query.field("blocks")
@graphql_payload
@require_authentication
async def get_blocks(_, info, location_ids: List[int] = None) -> List[UnitOutput]:
    await update_units_map(info.context, location_ids=location_ids)
    units_map = info.context.get('units_map')
    block_roots = info.context.get('block_roots')
    return [units_map.get(i) for i in block_roots]

@graphql_query.field("blocksUnits")
@graphql_payload
@require_authentication
async def get_units(_, info, unit_ids: List[int]) -> List[UnitOutput]:
    await update_units_map(info.context, unit_ids=unit_ids)
    units_map = info.context.get('units_map')
    return [units_map.get(i) for i in unit_ids]

@unit.field("subject")
async def resolve_subject(obj, info):
    await update_ontology_map(info.context, entry_ids=[obj.subject])
    ontology_map = info.context.get('ontology_map')
    return ontology_map.get(obj.subject)

@unit.field("germplasm")
async def resolve_germplasm(obj, info):
    await update_germplasm_map(info.context, entry_ids=[obj.germplasm])
    germplasm_map = info.context.get('germplasm_map')
    return germplasm_map.get(obj.germplasm)

@unit.field("positions")
async def resolve_positions(obj, _):
    return [Position(**p) for p in obj.positions]

@unit.field("parents")
async def resolve_parents(obj, info):
    await update_units_map(info.context, unit_ids=obj.parents)
    units_map = info.context.get('units_map')
    return [units_map.get(i) for i in obj.parents]

@unit.field("children")
async def resolve_children(obj, info):
    await update_units_map(info.context, unit_ids=obj.children)
    units_map = info.context.get('units_map')
    return [units_map.get(i) for i in obj.children]

@position.field("location")
async def resolve_location(obj, info):
    await update_locations_map(info.context, location_ids=[obj.location_id])
    locations_map = info.context.get('locations_map')
    return locations_map.get(obj.location_id)

@position.field("layout")
async def resolve_layout(obj, info):
    if obj.layout_id is None:
        return None
    await update_layouts_map(info.context, layout_ids=[obj.layout_id])
    layouts_map = info.context.get('layouts_map')
    return layouts_map.get(obj.layout_id)

