from ariadne import ObjectType

from src.breedgraph.entrypoints.fastapi.graphql.decorators import graphql_payload, require_authentication
from src.breedgraph.entrypoints.fastapi.graphql.resolvers.queries.context_loaders import (
    update_layouts_map,
    inject_ontology
)
from src.breedgraph.entrypoints.fastapi.graphql.resolvers.queries import graphql_query

from src.breedgraph.domain.model.arrangements import LayoutOutput
from typing import List

import logging
logger = logging.getLogger(__name__)

layout = ObjectType("Layout")

@graphql_query.field("arrangements")
@graphql_payload
@require_authentication
async def get_arrangements(_, info, location_id: int|None = None) -> List[LayoutOutput]:
    await update_layouts_map(info.context, location_id)
    layouts_map = info.context.get('layouts_map')
    arrangement_roots = info.context.get('arrangement_roots')
    return [layouts_map.get(i) for i in arrangement_roots]

@graphql_query.field("layout")
@graphql_payload
@require_authentication
async def get_layout(_, info, layout_id: int) -> LayoutOutput:
    await update_layouts_map(info.context, layout_id=layout_id)
    layouts_map = info.context.get('layouts_map')
    return layouts_map.get(layout_id, None)

@layout.field("parent")
def resolve_parent(obj, info):
    return info.context.get('layouts_map').get(obj.parent)

@layout.field("children")
def resolve_children(obj, info):
    return [info.context.get('layouts_map').get(child) for child in obj.children]

@layout.field("release")
def resolve_release(obj, info):
    return obj.release.name

@layout.field("type")
async def resolve_type(obj, info):
    await inject_ontology(info.context, entry_id=obj.type)
    ontology = info.context.get('ontology')
    return ontology.to_output(obj.type)
