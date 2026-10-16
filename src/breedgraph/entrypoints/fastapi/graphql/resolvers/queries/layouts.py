from ariadne import ObjectType

from breedgraph.service_layer.queries.read_models.ontology import OntologyEntryOutput, OntologyViewMode
from breedgraph.domain.model.location_trees import LocationOutput
from breedgraph.entrypoints.fastapi.graphql.decorators import graphql_payload
from breedgraph.entrypoints.fastapi.graphql.resolvers.queries.context_loaders import (
    update_layouts_map,
    update_ontology_map,
    update_locations_map
)


from breedgraph.domain.model.layout_trees import LayoutOutput


import logging
logger = logging.getLogger(__name__)

from . import graphql_query
from ..registry import graphql_resolvers
layout = ObjectType("Layout")
graphql_resolvers.register_type_resolvers(layout)

@graphql_query.field("layoutsRoots")
@graphql_payload
async def get_layout_trees(_, info, location_id: int) -> list[LayoutOutput]:
    return await update_layouts_map(info.context, location_id=location_id)

@graphql_query.field("layoutsLayouts")
@graphql_payload
async def get_layouts(_, info, ids: list[int]) -> list[LayoutOutput]:
    return await update_layouts_map(info.context, layout_ids=ids)

@layout.field("root")
async def resolve_layout_tree(obj, info) -> LayoutOutput:
    await update_layouts_map(info.context, layout_ids=[obj.root])
    return info.context.get('layouts_map').get(obj.root)

@layout.field("parent")
async def resolve_parent(obj, info) -> LayoutOutput:
    await update_layouts_map(info.context, layout_ids=[obj.parent])
    return info.context.get('layouts_map').get(obj.parent)

@layout.field("children")
async def resolve_children(obj, info) -> list[LayoutOutput]:
    await update_layouts_map(info.context, layout_ids=obj.children)
    return [info.context.get('layouts_map').get(child) for child in obj.children]

@layout.field("type")
async def resolve_type(obj, info) -> OntologyEntryOutput:
    await update_ontology_map(info.context, entry_ids=[obj.type], view=OntologyViewMode.REFERENTIAL)
    ontology_map = info.context.get('ontology_map')
    return ontology_map.get(obj.type)

@layout.field("location")
async def resolve_location(obj: LayoutOutput, info):
    if obj.location is None:
        return None
    await update_locations_map(info.context, location_ids=[obj.location])
    locations_map = info.context.get('locations_map')
    location = locations_map.get(obj.location)
    if location is None:
        return LocationOutput(id=obj.location, name='REDACTED')
    return location
