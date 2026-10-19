"""Adding countries and placing locations request detailed maps (adapters/pmtiles/map_regions.py)"""
import pytest

from breedgraph.domain.commands.location_trees import CreateLocation, UpdateLocation, DeleteLocation, GeoCoordinate
from breedgraph.service_layer.handlers import handlers
from breedgraph.service_layer.infrastructure import AbstractMapRegions


class RecordingMapRegions(AbstractMapRegions):
    def __init__(self):
        self.calls = []

    async def start(self):
        pass

    async def stop(self):
        pass

    async def request_country(self, code, requested_by=None):
        self.calls.append(('country', code, requested_by))

    async def request_places(self, code, coordinates, requested_by=None):
        self.calls.append(('places', code, list(coordinates), requested_by))

    async def remove_country(self, code):
        self.calls.append(('remove', code))


@pytest.fixture
def map_regions(monkeypatch) -> RecordingMapRegions:
    regions = RecordingMapRegions()
    monkeypatch.setitem(handlers.dependencies, 'map_regions', regions)
    return regions


async def get_tree(uow_factory, user_id: int, **kwargs):
    async with uow_factory.get_uow(user_id=user_id) as uow:
        return await uow.repositories.location_trees.get(**kwargs)


def points(*coordinates):
    return [GeoCoordinate(latitude=latitude, longitude=longitude) for latitude, longitude in coordinates]


@pytest.mark.asyncio(loop_scope="session")
async def test_countries_and_placed_locations_request_maps(
        bus, event_queue, uow_factory, location_tree_build_context, map_regions
):
    context = location_tree_build_context
    user_id, team_id = context['user_id'], context['team_id']

    async def handle(command):
        await bus.handle(command)
        await event_queue.join()

    await handle(CreateLocation(
        agent_id=user_id, write_team=team_id, type_id=context['ontology_location_country'], name='Luxembourg',
        code='LUX', coordinates=points((49.8, 6.1))
    ))
    country_id = (await get_tree(uow_factory, user_id, code='LUX')).root.id
    # a country's own coordinates, like the centre the map saves, place nothing
    assert map_regions.calls == [('country', 'LUX', user_id)]

    async def create(name: str, coordinates=None):
        await handle(CreateLocation(
            agent_id=user_id, write_team=team_id, type_id=context['ontology_location_field'], name=name,
            parent_id=country_id, **({'coordinates': coordinates} if coordinates else {})
        ))
        tree = await get_tree(uow_factory, user_id, location_id=country_id)
        return next(location for location in tree.entries.values() if location.name == name)

    map_regions.calls.clear()
    field = await create('A field', points((49.6, 6.1), (49.7, 6.1), (49.7, 6.2)))
    assert [(c['latitude'], c['longitude']) for c in field.coordinates] == [(49.6, 6.1), (49.7, 6.1), (49.7, 6.2)]
    assert map_regions.calls == [('places', 'LUX', [(49.6, 6.1), (49.7, 6.1), (49.7, 6.2)], user_id)]

    map_regions.calls.clear()
    unplaced = await create('A field without coordinates')
    assert map_regions.calls == []

    async def update(location_id: int, coordinates):
        await handle(UpdateLocation(agent_id=user_id, location_id=location_id, coordinates=coordinates))

    await update(field.id, points((49.6, 6.1), (49.7, 6.1), (49.7, 6.2)))  # unchanged
    await update(unplaced.id, [])  # empty
    await update(country_id, points((49.7, 6.0)))  # a country
    await handle(UpdateLocation(agent_id=user_id, location_id=field.id, name='Renamed'))  # no coordinates given
    assert map_regions.calls == []

    await update(unplaced.id, points((49.5, 6.0)))
    await update(field.id, points((49.6, 6.2)))
    assert map_regions.calls == [
        ('places', 'LUX', [(49.5, 6.0)], user_id),
        ('places', 'LUX', [(49.6, 6.2)], user_id)
    ]

    map_regions.calls.clear()
    await handle(DeleteLocation(agent_id=user_id, location_id=field.id))
    await handle(DeleteLocation(agent_id=user_id, location_id=unplaced.id))
    assert map_regions.calls == []
    await handle(DeleteLocation(agent_id=user_id, location_id=country_id))
    assert map_regions.calls == [('remove', 'LUX')]
