from ariadne import ObjectType

from src.breedgraph.entrypoints.fastapi.graphql.resolvers.queries import graphql_query
from src.breedgraph.entrypoints.fastapi.graphql.decorators import graphql_payload

from src.breedgraph.entrypoints.fastapi.graphql.resolvers.queries.context_loaders import (
    update_units_map,
    inject_ontology
)

from src.breedgraph.domain.model.blocks import UnitOutput

from typing import List

import logging
logger = logging.getLogger(__name__)

unit = ObjectType("Unit")

@graphql_query.field("blocks")
@graphql_payload
async def get_blocks(_, info, location_id: int = None) -> List[UnitOutput]:
    await update_units_map(info.context, location_id)
    units_map = info.context.get('units_map')
    block_roots = info.context.get('block_roots')
    return [units_map.get(i) for i in block_roots]

@graphql_query.field("unit")
@graphql_payload
async def get_unit(_, info, unit_id: int) -> List[UnitOutput]:
    await update_units_map(info.context, unit_id=unit_id)
    units_map = info.context.get('units_map')
    return units_map[unit_id]

@unit.field("subject")
async def resolve_subject(obj, info):
    await inject_ontology(info.context, entry_id=obj.subject)
    ontology = info.context.get('ontology')
    import pdb; pdb.set_trace()
    return ontology.to_output(obj.subject)

@unit.field("release")
def resolve_release(obj, info):
    return obj.release.name