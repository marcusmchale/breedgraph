from ariadne import ObjectType


from src.breedgraph.entrypoints.fastapi.graphql.decorators import graphql_payload, require_authentication
from src.breedgraph.entrypoints.fastapi.graphql.resolvers.queries.context_loaders import (
    update_units_map,
    update_ontology_map
)

from src.breedgraph.domain.model.blocks import UnitOutput

from typing import List

import logging
logger = logging.getLogger(__name__)

from . import graphql_query
from ..registry import graphql_resolvers
unit = ObjectType("Unit")
graphql_resolvers.register_type_resolvers(unit)

@graphql_query.field("blocks")
@graphql_payload
@require_authentication
async def get_blocks(_, info, location: int = None) -> List[UnitOutput]:
    await update_units_map(info.context, location)
    units_map = info.context.get('units_map')
    block_roots = info.context.get('block_roots')
    return [units_map.get(i) for i in block_roots]

@graphql_query.field("unit")
@graphql_payload
@require_authentication
async def get_unit(_, info, unit_id: int) -> List[UnitOutput]:
    await update_units_map(info.context, unit_id=unit_id)
    units_map = info.context.get('units_map')
    return units_map[unit_id]

@unit.field("subject")
async def resolve_subject(obj, info):
    await update_ontology_map(info.context, entry=obj.subject)
    ontology = info.context.get('ontology')
    return ontology.to_output(obj.subject)

@unit.field("release")
def resolve_release(obj, info):
    return obj.release.name