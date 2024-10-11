from ariadne import ObjectType
from src.breedgraph.views.regions import countries

from src.breedgraph.domain.model.regions import LocationInput, LocationOutput
from src.breedgraph.entrypoints.fastapi.graphql.decorators import graphql_payload

from src.breedgraph.entrypoints.fastapi.graphql.resolvers.queries.context_loaders import (
    update_locations_map,
    inject_ontology
)

from src.breedgraph.entrypoints.fastapi.graphql.resolvers.queries import graphql_query

from typing import List

import logging
logger = logging.getLogger(__name__)

location = ObjectType("Location")

@graphql_query.field("countries")
@graphql_payload
async def get_countries(_, info) -> List[LocationInput|LocationOutput]:
    bus = info.context.get('bus')
    return [c async for c in countries(bus.read_model)]

@graphql_query.field("regions")
@graphql_payload
async def get_regions(_, info) -> List[LocationOutput]:
    await update_locations_map(info.context)
    locations_map = info.context.get('locations_map')
    region_roots = info.context.get('region_roots')
    return [locations_map.get(i) for i in region_roots]

@graphql_query.field("location")
@graphql_payload
async def get_location(_, info, location_id: int) -> LocationOutput:
    await update_locations_map(info.context, location_id=location_id)
    locations_map = info.context.get('locations_map')
    return locations_map.get(location_id, None)

@location.field("parent")
def resolve_parent(obj, info):
    return info.context.get('locations_map').get(obj.parent)

@location.field("children")
def resolve_children(obj, info):
    return [info.context.get('locations_map').get(child) for child in obj.children]

@location.field("release")
def resolve_release(obj, info):
    return obj.release.name

@location.field("type")
async def resolve_type(obj, info):
    await inject_ontology(info.context, entry_id=obj.type)
    ontology = info.context.get('ontology')
    return ontology.to_output(obj.type)
