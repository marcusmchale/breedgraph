from ariadne import ObjectType

from src.breedgraph.domain.model.ontology import OntologyEntryOutput
from src.breedgraph.entrypoints.fastapi.graphql.decorators import graphql_payload, require_authentication
from src.breedgraph.entrypoints.fastapi.graphql.resolvers.queries.context_loaders import (
    update_layouts_map,
    update_ontology_map
)


from src.breedgraph.domain.model.arrangements import LayoutOutput
from typing import List

import logging
logger = logging.getLogger(__name__)

from . import graphql_query
from ..registry import graphql_resolvers
layout = ObjectType("Layout")
graphql_resolvers.register_type_resolvers(layout)

@graphql_query.field("arrangements")
@graphql_payload
@require_authentication
async def get_arrangements(_, info, location_id: int|None = None) -> List[LayoutOutput]:
    await update_layouts_map(info.context, location_id=location_id)
    layouts_map = info.context.get('layouts_map')
    arrangement_roots = info.context.get('arrangement_roots')
    return [layouts_map.get(i) for i in arrangement_roots]

@graphql_query.field("arrangementsLayouts")
@graphql_payload
@require_authentication
async def get_layouts(_, info, layout_ids: List[int]) -> List[LayoutOutput]:
    await update_layouts_map(info.context, layout_ids=layout_ids)
    layouts_map = info.context.get('layouts_map')
    return [layouts_map.get(i) for i in layout_ids]

@layout.field("parent")
async def resolve_parent(obj, info) -> LayoutOutput:
    await update_layouts_map(info.context, layout_ids=[obj.parent])
    return info.context.get('layouts_map').get(obj.parent)

@layout.field("children")
async def resolve_children(obj, info) -> List[LayoutOutput]:
    await update_layouts_map(info.context, layout_ids=obj.children)
    return [info.context.get('layouts_map').get(child) for child in obj.children]

@layout.field("type")
async def resolve_type(obj, info) -> OntologyEntryOutput:
    await update_ontology_map(info.context, entry_ids=[obj.type])
    ontology_map = info.context.get('ontology_map')
    return ontology_map.get(obj.type)
