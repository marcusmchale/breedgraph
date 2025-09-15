from ariadne import ObjectType
from src.breedgraph.service_layer.queries.read_models import regions

from src.breedgraph.domain.model.regions import LocationInput, LocationOutput
from src.breedgraph.entrypoints.fastapi.graphql.decorators import graphql_payload, require_authentication

from src.breedgraph.entrypoints.fastapi.graphql.resolvers.queries.context_loaders import (
    update_locations_map,
    update_ontology_map
)

from typing import List

import logging
logger = logging.getLogger(__name__)

from . import graphql_query
from ..registry import graphql_resolvers
location = ObjectType("Location")
graphql_resolvers.register_type_resolvers(location)

@graphql_query.field("countries")
@graphql_payload
@require_authentication
async def get_countries(_, info) -> List[LocationInput|LocationOutput]:
    bus = info.context.get('bus')
    return [c async for c in regions.countries(bus.read_model)]

@graphql_query.field("regions")
@graphql_payload
@require_authentication
async def get_regions(_, info) -> List[LocationOutput]:
    await update_locations_map(info.context)
    locations_map = info.context.get('locations_map')
    region_roots = info.context.get('region_roots')
    return [locations_map.get(i) for i in region_roots]

@graphql_query.field("location")
@graphql_payload
@require_authentication
async def get_location(_, info, location: int) -> LocationOutput:
    await update_locations_map(info.context, location_id=location)
    locations_map = info.context.get('locations_map')
    return locations_map.get(location, None)

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
    await update_ontology_map(info.context, entry=obj.type)
    ontology = info.context.get('ontology')
    return ontology.to_output(obj.type)
