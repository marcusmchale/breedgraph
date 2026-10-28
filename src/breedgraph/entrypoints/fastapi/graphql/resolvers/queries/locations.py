from ariadne import ObjectType

from breedgraph.service_layer.queries.read_models import OntologyViewMode
from breedgraph.service_layer.queries.views import location_trees, AbstractLocationTreesView

from breedgraph import config
from breedgraph.custom_exceptions import IllegalOperationError
from breedgraph.domain.model.location_trees import LocationInput, LocationOutput
from breedgraph.service_layer.infrastructure.gazetteer import Place, PlacesStatus
from breedgraph.service_layer.infrastructure.map_regions import CountryMapStatus, MapState
from breedgraph.adapters.pmtiles.regions import Region
from breedgraph.entrypoints.fastapi.graphql.decorators import graphql_payload

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
country_map_status = ObjectType("CountryMapStatus")
graphql_resolvers.register_type_resolvers(location, location_template, location_type_locations, country_map_status)

PLACE_SEARCHES_PER_REQUEST = 5

@graphql_query.field("locationsCountries")
@graphql_payload
async def get_countries(_, info) -> List[LocationInput]:
    bus = info.context.get('bus')
    async with bus.views_factory.get_views(user_id = info.context.get('user_id')) as views:
        return await views.location_trees.countries()

@graphql_query.field("locationsSearch")
@graphql_payload
async def search_locations(_, info, name: str, limit: int | None = None) -> List[LocationOutput]:
    bus = info.context.get('bus')
    async with bus.views_factory.get_views(user_id=info.context.get('user_id')) as views:
        locations = await views.location_trees.search_locations(name, limit=limit or 10)
    info.context.setdefault('locations_map', dict()).update({location_.id: location_ for location_ in locations})
    return locations

def _country_code(code: str) -> str:
    try:
        return Region(code).code
    except ValueError:
        raise IllegalOperationError(f"Not an ISO 3166 alpha-3 code: {code!r}")

@graphql_query.field("locationsSearchPlaces")
@graphql_payload
async def search_places(
        _,
        info,
        query: str,
        viewbox: List[float] | None = None,
        bounded: bool | None = None,
        country: str | None = None,
        limit: int | None = None
) -> List[Place]:
    """
    Open to visitors: answered on this server from its copy of GeoNames' places, so no search leaves it, a few at a
    time and each within a second (adapters/geonames/gazetteer.py)
    """
    searches = info.context['place_searches'] = info.context.get('place_searches', 0) + 1
    if searches > PLACE_SEARCHES_PER_REQUEST:
        raise IllegalOperationError(f"At most {PLACE_SEARCHES_PER_REQUEST} place searches can be made in one request")
    gazetteer = info.context['bus'].gazetteer
    if gazetteer is None:
        raise IllegalOperationError("Place search is not available")
    return await gazetteer.search_places(
        query, viewbox=viewbox, bounded=bool(bounded), country=country and _country_code(country), limit=limit or 5
    )

@graphql_query.field("locationsCountryPlace")
@graphql_payload
async def get_country_place(_, info, code: str) -> Place | None:
    """Open to visitors, as the map files are"""
    gazetteer = info.context['bus'].gazetteer
    code = _country_code(code)
    return await gazetteer.country_place(code) if gazetteer is not None else None

@graphql_query.field("locationsMapStatus")
@graphql_payload
async def get_map_status(_, info, code: str) -> CountryMapStatus:
    """Open to visitors, as the map files themselves are"""
    map_regions = info.context['bus'].map_regions
    try:
        if map_regions is None:
            Region(code)
            return CountryMapStatus(code, MapState.NONE, int(config.MAP_REGION_MAX_GB * 10 ** 9), False)
        return await map_regions.status(code)
    except ValueError:
        raise IllegalOperationError(f"Not an ISO 3166 alpha-3 code: {code!r}")

@country_map_status.field("places")
async def resolve_places_status(obj: CountryMapStatus, info) -> PlacesStatus:
    gazetteer = info.context['bus'].gazetteer
    if gazetteer is None:
        return PlacesStatus(MapState.NONE, False, False)
    return await gazetteer.status(obj.code)

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
