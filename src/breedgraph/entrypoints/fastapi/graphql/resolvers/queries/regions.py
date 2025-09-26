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

@graphql_query.field("regionsCountries")
@graphql_payload
@require_authentication
async def get_countries(_, info) -> List[LocationInput|LocationOutput]:
    bus = info.context.get('bus')
    countries = [c async for c in regions.countries(bus.read_model)]
    return countries

@graphql_query.field("regions")
@graphql_payload
@require_authentication
async def get_regions(_, info) -> List[LocationOutput]:
    await update_locations_map(info.context)
    locations_map = info.context.get('locations_map')
    region_roots = info.context.get('region_roots')
    return [locations_map.get(i) for i in region_roots]

@graphql_query.field("regionsLocations")
@graphql_payload
@require_authentication
async def get_locations(_, info, location_type_id: int) -> List[LocationOutput]:
    user_id = info.context.get('user_id')
    bus = info.context.get('bus')
    locations_map = info.context.get('locations_map', dict())
    locations_by_type = []
    async with bus.uow.get_uow(user_id = user_id) as uow:
        async for location_ in uow.views.regions.get_locations_by_type(location_type_id = location_type_id):
            locations_map[location_.id] = location_
            locations_by_type.append(location_.id)
        return [locations_map.get(i) for i in locations_by_type]

@graphql_query.field("regionsLocation")
@graphql_payload
@require_authentication
async def get_location(_, info, location_id: int) -> LocationOutput | None:
    await update_locations_map(info.context, location_ids=[location_id])
    locations_map = info.context.get('locations_map')
    return locations_map.get(location_id)

@location.field("parent")
async def resolve_parent(obj, info) -> LocationOutput:
    await update_locations_map(info.context, location_ids=[obj.parent])
    return info.context.get('locations_map').get(obj.parent)

@location.field("children")
async def resolve_children(obj, info):
    await update_locations_map(info.context, location_ids=obj.children)
    return [info.context.get('locations_map').get(child) for child in obj.children]

@location.field("type")
async def resolve_type(obj, info):
    await update_ontology_map(info.context, entry_ids=[obj.type])
    ontology_map = info.context.get('ontology_map')
    return ontology_map.get(obj.type)
