from breedgraph.domain import events
from breedgraph.service_layer.infrastructure import AbstractMapRegions, AbstractUnitOfWorkFactory

from ..registry import handlers

import logging
logger = logging.getLogger(__name__)


@handlers.event_handler()
async def fetch_country_maps(
        event: events.location_trees.CountryAdded,
        map_regions: AbstractMapRegions
):
    await map_regions.request_country(event.code)


@handlers.event_handler()
async def fetch_location_maps(
        event: events.location_trees.LocationPlaced,
        uow_factory: AbstractUnitOfWorkFactory,
        map_regions: AbstractMapRegions
):
    """The coordinates are read here, as the user who placed the location, so they are not in the event's log"""
    async with uow_factory.get_uow(user_id=event.agent_id) as uow:
        location_tree = await uow.repositories.location_trees.get(location_id=event.location_id)
        if location_tree is None or location_tree.root.id == event.location_id:
            return
        location = location_tree.get_location(event.location_id)
        code = location_tree.root.code
        points = [(coordinate['latitude'], coordinate['longitude']) for coordinate in location.coordinates or []]
    await map_regions.request_places(code, points)


@handlers.event_handler()
async def remove_country_maps(
        event: events.location_trees.CountryRemoved,
        map_regions: AbstractMapRegions
):
    await map_regions.remove_country(event.code)

