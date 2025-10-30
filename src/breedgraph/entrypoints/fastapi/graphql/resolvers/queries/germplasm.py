from ariadne import ObjectType
from src.breedgraph.domain.model.germplasm import (
    GermplasmOutput, GermplasmRelationship
)
from src.breedgraph.entrypoints.fastapi.graphql.decorators import graphql_payload, require_authentication
from src.breedgraph.entrypoints.fastapi.graphql.resolvers.queries.context_loaders import update_germplasm_map

from typing import List

import logging

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
        entry_ids: List[int] = None,
        names: List[str] = None,
) -> List[GermplasmOutput]:
    await update_germplasm_map(info.context, entry_ids=entry_ids, names=names)
    return [value for key, value in info.context.get('germplasm_map').items()]

@graphql_query.field("germplasmCrops")
@graphql_payload
@require_authentication
async def get_germplasm_crops(
        _,
        info
) -> List[GermplasmOutput]:
    bus = info.context.get('bus')
    user_id = info.context.get('user_id')
    async with bus.uow.get_uow(user_id=user_id) as uow:
        return [entry async for entry in uow.germplasm.get_root_entries(as_output=True)]

async def resolve_germplasm_entries(context, entry_ids):
    await update_germplasm_map(context, entry_ids=entry_ids)
    germplasm_map = context.get('germplasm_map')
    return [germplasm_map[entry_id] for entry_id in entry_ids]

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