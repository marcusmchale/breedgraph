from ariadne import ObjectType

from breedgraph.service_layer.queries.read_models import OntologyViewMode
from breedgraph.service_layer.queries.views import location_trees, AbstractLocationTreesView

from breedgraph import config
from breedgraph.custom_exceptions import IllegalOperationError
from breedgraph.domain.model.location_trees import LocationInput, LocationOutput
from breedgraph.service_layer.infrastructure.geocoding import Place
from breedgraph.entrypoints.fastapi.graphql.decorators import graphql_payload, require_authentication

from breedgraph.entrypoints.fastapi.graphql.resolvers.queries.context_loaders import (
    update_locations_map,
    update_ontology_map
)

from typing import List

import logging
logger = logging.getLogger(__name__)

from . import graphql_query
from ..registry import graphql_resolvers
location = ObjectType("Location")
location_template = ObjectType("LocationTemplate")
location_type_locations = ObjectType("LocationTypeLocations")
graphql_resolvers.register_type_resolvers(location, location_template, location_type_locations)

@graphql_query.field("locationsCountries")
@graphql_payload
async def get_countries(_, info) -> List[LocationInput]:
    bus = info.context.get('bus')
    async with bus.views_factory.get_views(user_id = info.context.get('user_id')) as views:
        return await views.location_trees.countries()

async def _geocoding(info):
    """The geocoding service, once the user is within their hourly limit of searches"""
    state_store = info.context['bus'].state_store
    searches = await state_store.increment_rate_counter(f"geocoding:{info.context['user_id']}", window_seconds=3600)
    if searches > config.GEOCODING_RATE_LIMIT_PER_HOUR:
        raise IllegalOperationError("You have reached the limit of place searches per hour, please try again later")
    return info.context['geocoding_service']

@graphql_query.field("locationsSearchPlaces")
@graphql_payload
@require_authentication
async def search_places(
        _,
        info,
        query: str,
        viewbox: List[float] | None = None,
        bounded: bool | None = None,
        country_code: str | None = None,
        limit: int | None = None
) -> List[Place]:
    geocoding = await _geocoding(info)
    return await geocoding.search_places(
        query, viewbox=viewbox, bounded=bool(bounded), country_code=country_code, limit=limit or 5
    )

@graphql_query.field("locationsGeocodeCountry")
@graphql_payload
@require_authentication
async def geocode_country(_, info, name: str) -> Place | None:
    geocoding = await _geocoding(info)
    return await geocoding.geocode_country(name)

@graphql_query.field("locationsRoots")
@graphql_payload
async def get_location_trees(_, info) -> List[LocationOutput]:
    return await update_locations_map(info.context)

@graphql_query.field("locationsLocations")
@graphql_payload
async def get_locations(_, info, ids: List[int]) -> List[LocationOutput]:
    return await update_locations_map(info.context, location_ids=ids)

@graphql_query.field("locationsLocationsByType")
@graphql_payload
async def get_locations_by_type(_, info, location_type_id: int | None = None) -> List[LocationOutput]:
    user_id = info.context.get('user_id')
    bus = info.context.get('bus')
    async with bus.views_factory.get_views(user_id=user_id) as views:
        locations = await views.location_trees.get_locations_by_type(location_type = location_type_id)
    info.context.setdefault('locations_map', dict()).update({location_.id: location_ for location_ in locations})
    return locations

@location.field("root")
async def resolve_location_tree(obj, info) -> LocationOutput:
    await update_locations_map(info.context, location_ids=[obj.root])
    return info.context.get('locations_map').get(obj.root)

@location.field("parent")
async def resolve_parent(obj, info) -> LocationOutput:
    await update_locations_map(info.context, location_ids=[obj.parent])
    return info.context.get('locations_map').get(obj.parent)

@location.field("children")
async def resolve_children(obj, info):
    await update_locations_map(info.context, location_ids=obj.children)
    return [info.context.get('locations_map').get(child) for child in obj.children]

@graphql_query.field("locationsDescendantsByType")
@graphql_payload
async def get_descendants_by_type(_, info, location_ids: List[int]) -> List[dict]:
    bus = info.context.get('bus')
    async with bus.views_factory.get_views(user_id=info.context.get('user_id')) as views:
        by_type = await views.location_trees.get_descendants_by_type(location_ids=location_ids)
    return [{'type': type_id, 'locations': locations} for type_id, locations in by_type.items()]

@location_type_locations.field("type")
async def resolve_location_type_locations_type(obj, info):
    if obj.get('type') is None:
        return None
    await update_ontology_map(info.context, entry_ids=[obj['type']], view=OntologyViewMode.REFERENTIAL)
    return info.context.get('ontology_map').get(obj['type'])

@location.field("type")
async def resolve_type(obj, info):
    await update_ontology_map(info.context, entry_ids=[obj.type], view=OntologyViewMode.REFERENTIAL)
    ontology_map = info.context.get('ontology_map')
    return ontology_map.get(obj.type)

@location_template.field("typeId")
async def resolve_type(obj, _):
    return obj.type
