from typing import List

from breedgraph.domain import events
from breedgraph.service_layer.infrastructure import AbstractMapRegions, AbstractNotifications, AbstractUnitOfWorkFactory
from ...infrastructure.notifications import email_templates

from ..registry import handlers

import logging
logger = logging.getLogger(__name__)


@handlers.event_handler()
async def fetch_country_maps(
        event: events.location_trees.CountryAdded,
        map_regions: AbstractMapRegions
):
    await map_regions.request_country(event.code, requested_by=event.agent_id)


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
    await map_regions.request_places(code, points, requested_by=event.agent_id)


@handlers.event_handler()
async def remove_country_maps(
        event: events.location_trees.CountryRemoved,
        map_regions: AbstractMapRegions
):
    await map_regions.remove_country(event.code)


async def _notify(
        uow_factory: AbstractUnitOfWorkFactory,
        notifications: AbstractNotifications,
        user_ids: List[int],
        message: email_templates.Email
):
    async with uow_factory.get_uow() as uow:
        accounts = [await uow.repositories.accounts.get(user_id=user_id) for user_id in user_ids]
    users = [account.user for account in accounts if account is not None]
    if users:
        await notifications.send(users, message)


@handlers.event_handler()
async def notify_map_region_fetching(
        event: events.location_trees.MapRegionFetching,
        uow_factory: AbstractUnitOfWorkFactory,
        notifications: AbstractNotifications
):
    await _notify(uow_factory, notifications, event.user_ids, email_templates.MapRegionFetching(event.name))


@handlers.event_handler()
async def notify_map_country_divided(
        event: events.location_trees.MapCountryDivided,
        uow_factory: AbstractUnitOfWorkFactory,
        notifications: AbstractNotifications
):
    await _notify(uow_factory, notifications, event.user_ids, email_templates.MapCountryDivided(event.name))


@handlers.event_handler()
async def notify_map_region_ready(
        event: events.location_trees.MapRegionReady,
        uow_factory: AbstractUnitOfWorkFactory,
        notifications: AbstractNotifications
):
    await _notify(uow_factory, notifications, event.user_ids, email_templates.MapRegionReady(event.name))


@handlers.event_handler()
async def notify_map_region_failed(
        event: events.location_trees.MapRegionFailed,
        uow_factory: AbstractUnitOfWorkFactory,
        notifications: AbstractNotifications
):
    await _notify(uow_factory, notifications, event.user_ids, email_templates.MapRegionFailed(event.name))
