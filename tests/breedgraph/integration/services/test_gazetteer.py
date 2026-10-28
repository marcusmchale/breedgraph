"""
The place search's service (adapters/geonames/gazetteer.py) with the real state store and GeoNames' site answered from
the files in tests/map_worker/geonames_fixtures.py, so no request leaves the test. Each test runs twice: with the API
downloading the files itself, and with the map worker (src/map_worker) fetching them for it, run here with a client
calling the state store and what the API's routes call.
"""
import asyncio
import json
import logging
import sqlite3
import zipfile

import httpx
import pytest
import pytest_asyncio

from breedgraph.adapters.geonames import GeoNamesGazetteer
from breedgraph.adapters.geonames import gazetteer as gazetteer_module, index as index_module
from breedgraph.adapters.pmtiles.map_regions import FAILED_UNKNOWN
from breedgraph.custom_exceptions import IllegalOperationError
from breedgraph.service_layer.infrastructure.map_regions import MapState
from map_worker import fetching
from map_worker.fetching import PmtilesCommand
from map_worker.service_layer.handlers import MapHandlers
from map_worker.service_layer.worker import MapWorker
from tests.breedgraph.integration.services.map_worker_harness import InProcessClient, until
from tests.map_worker.geonames_fixtures import GEONAMES_URL, place, write_site, serving

REAL_CLIENT = httpx.AsyncClient


class Places:
    """GeoNames' site, the requests made of it, and the place search's folder"""

    def __init__(self, path, state_store, worker: bool):
        self.state_store = state_store
        self.worker = worker
        self.site = write_site(path / 'site')
        self.requests = []
        self.gate: asyncio.Event | None = None  # while set, Ireland's file waits for it to be released
        self.held = []  # the requests waiting for it
        self.path = path / 'gazetteer'
        self.work = path / 'work'
        self.client = InProcessClient(state_store, path / 'boundaries', path / 'tiles', places=self.path / 'places')
        self.map_worker: MapWorker | None = None
        self.running: asyncio.Task | None = None

    async def handle(self, request: httpx.Request) -> httpx.Response:
        if self.gate is not None and request.url.path.endswith('/IE.zip'):
            self.held.append(request.url.path)
            await self.gate.wait()
        return serving(self.site, self.requests)(request)

    def downloads(self) -> list:
        return [path.rsplit('/', 1)[-1] for path in self.requests if path.endswith('.zip')]

    def service(self, geonames_url: str = GEONAMES_URL) -> GeoNamesGazetteer:
        return GeoNamesGazetteer(
            self.state_store, path=self.path, worker=self.worker, geonames_url='' if self.worker else geonames_url,
            poll_seconds=0.05
        )

    def start_worker(self):
        handlers = MapHandlers(PmtilesCommand(''), self.work, '', '', geonames_url=GEONAMES_URL)
        handlers.clear()
        self.map_worker = MapWorker(self.client, handlers, poll_interval=0.05)
        self.running = asyncio.create_task(self.map_worker.run())

    async def stop_worker(self):
        if self.running is not None:
            await self.map_worker.shutdown()
            await asyncio.wait_for(self.running, 10)
            self.running = None


@pytest_asyncio.fixture(loop_scope="session", params=['api', 'worker'])
async def places(request, tmp_path, state_store, monkeypatch) -> Places:
    async def clear():
        async for key in state_store.connection.scan_iter(match='map:*'):
            await state_store.connection.delete(key)
    await clear()
    places = Places(tmp_path, state_store, worker=request.param == 'worker')
    monkeypatch.setattr(fetching.httpx, 'AsyncClient',
                        lambda **kwargs: REAL_CLIENT(transport=httpx.MockTransport(places.handle), **kwargs))
    if places.worker:
        places.start_worker()
    yield places
    await places.stop_worker()
    await clear()


async def started(places: Places) -> GeoNamesGazetteer:
    gazetteer = places.service()
    await gazetteer.start()
    await gazetteer.wait_until_idle()
    return gazetteer


def names(found) -> list:
    return [(place.name, place.region) for place in found]


@pytest.mark.asyncio(loop_scope="session")
async def test_the_worlds_towns_are_fetched_at_the_first_start_and_a_country_added_is_searchable(places):
    gazetteer = await started(places)
    assert places.downloads() == ['cities1000.zip', 'shapes_simplified_low.json.zip']
    assert names(await gazetteer.search_places('galway')) == [('Galway', 'County Galway, Connacht')]
    status = await gazetteer.status('IRL')
    assert (status.state, status.enabled, status.towns) == (MapState.NONE, True, True)
    assert (await gazetteer.country_place('IRL')).bounds == [[51.4, -10.5], [55.4, -6.0]]

    await gazetteer.request_country('IRL')
    await gazetteer.wait_until_idle()
    assert places.downloads()[-1] == 'IE.zip'
    assert (await gazetteer.status('IRL')).state == MapState.READY
    assert len(await gazetteer.search_places('ballyduff')) == 3
    assert list((places.path / 'places').iterdir()) == [], 'the files are deleted once loaded'
    assert await places.state_store.get_pending_gazetteer() == []

    await gazetteer.stop()
    again = await started(places)
    assert len(places.downloads()) == 3, 'nothing is fetched again at the next start'
    assert len(await again.search_places('ballyduff')) == 3
    await again.stop()


@pytest.mark.asyncio(loop_scope="session")
async def test_a_country_removed_loses_its_places_but_not_the_worlds_towns(places):
    gazetteer = await started(places)
    await gazetteer.request_country('IRL')
    await gazetteer.wait_until_idle()

    await gazetteer.remove_country('IRL')
    assert await gazetteer.search_places('ballyduff') == []
    assert names(await gazetteer.search_places('galway')) == [('Galway', 'County Galway, Connacht')]
    assert (await gazetteer.status('IRL')).state == MapState.NONE
    await gazetteer.stop()


@pytest.mark.asyncio(loop_scope="session")
async def test_a_country_removed_while_its_places_are_fetched_is_not_loaded(places):
    gazetteer = await started(places)
    places.gate = asyncio.Event()
    await gazetteer.request_country('IRL')
    await until(lambda: places.held)

    await gazetteer.remove_country('IRL')
    places.gate.set()
    await gazetteer.wait_until_idle()
    assert await gazetteer.search_places('ballyduff') == []
    assert (await gazetteer.status('IRL')).state == MapState.NONE
    assert not (places.path / 'places' / 'IRL.tsv.gz').exists()
    assert await places.state_store.get_map_job('gazetteer', 'IRL') is None
    await gazetteer.stop()


@pytest.mark.asyncio(loop_scope="session")
async def test_a_failure_is_kept_for_the_map_and_retried_at_the_next_start(places):
    gazetteer = await started(places)
    await gazetteer.request_country('FRA')  # GeoNames' site, here, has no FR.zip
    await gazetteer.wait_until_idle()
    status = await gazetteer.status('FRA')
    assert (status.state, status.error) == (MapState.FAILED, FAILED_UNKNOWN)
    await gazetteer.stop()

    with zipfile.ZipFile(places.site / 'FR.zip', 'w') as archive:
        archive.writestr('FR.txt', place(2988507, 'Paris', 48.85, 2.35, 'P', 'PPLC', country='FR', population=2138551) + '\n')
    countries = places.state_store.connection
    listed = await countries.hget('country', 'FRA')
    await countries.hset('country', 'FRA', json.dumps({'id': 7, 'name': 'France', 'code': 'FRA'}))  # as when added
    try:
        again = await started(places)
        assert (await again.status('FRA')).state == MapState.READY, 'a country in the location trees without its places'
        assert [p.description for p in await again.search_places('paris')] == ['capital']
        await again.stop()
    finally:
        await countries.hset('country', 'FRA', listed)


@pytest.mark.asyncio(loop_scope="session")
async def test_a_fetch_interrupted_by_a_restart_is_resumed(places):
    gazetteer = await started(places)
    await gazetteer.stop()
    await places.state_store.add_gazetteer_request('IRL')
    again = await started(places)
    assert (await again.status('IRL')).state == MapState.READY
    await again.stop()


@pytest.mark.asyncio(loop_scope="session")
async def test_places_are_fetched_again_as_asked_and_fresh_from_the_map_workers_cache(places):
    gazetteer = await started(places)
    await gazetteer.request_country('IRL')
    await gazetteer.wait_until_idle()
    assert await gazetteer.fetch_now('IRL') is True
    assert await gazetteer.fetch_now('IRL', fresh=True) is True
    assert places.downloads().count('IE.zip') == 3, 'no file is kept here: the map worker\'s cache, if any, keeps them'
    if places.worker:
        assert [payload for kind, key, payload in places.client.payloads if key == 'IRL'][-2:] == [
            {'code': 'IE', 'fresh': False}, {'code': 'IE', 'fresh': True}
        ]
    assert len(await gazetteer.search_places('ballyduff')) == 3
    await gazetteer.stop()


@pytest.mark.asyncio(loop_scope="session")
@pytest.mark.parametrize('made_again', ['by another version', 'deleted'])
async def test_a_database_made_anew_has_its_places_fetched_again(places, made_again):
    gazetteer = await started(places)
    await gazetteer.request_country('IRL')
    await gazetteer.wait_until_idle()
    await gazetteer.stop()
    countries = places.state_store.connection
    listed = await countries.hget('country', 'IRL')
    await countries.hset('country', 'IRL', json.dumps({'id': 8, 'name': 'Ireland', 'code': 'IRL'}))  # as when added
    if made_again == 'deleted':  # as the demonstration site's reset does
        for path in places.path.glob('gazetteer.sqlite*'):
            path.unlink()
    else:
        with sqlite3.connect(places.path / 'gazetteer.sqlite') as db:
            db.execute('PRAGMA user_version = 0')
    try:
        again = await started(places)
        assert len(await again.search_places('ballyduff')) == 3, 'a country in the location trees'
        assert names(await again.search_places('qazvin')) == [('Qazvin', None)], 'its province named as it is'
        assert places.downloads().count('IE.zip') == 2 and places.downloads().count('cities1000.zip') == 2
        await again.stop()
    finally:
        await (countries.hset('country', 'IRL', listed) if listed is not None else countries.hdel('country', 'IRL'))


@pytest.mark.asyncio(loop_scope="session")
async def test_nothing_is_fetched_without_the_map_worker_or_geonames_url(places):
    if places.worker:
        pytest.skip('the map worker fetches whatever the API is configured with')
    gazetteer = places.service(geonames_url='')
    await gazetteer.start()
    await gazetteer.request_country('IRL')
    await gazetteer.wait_until_idle()
    assert places.requests == []
    status = await gazetteer.status('IRL')
    assert (status.state, status.enabled, status.towns) == (MapState.NONE, False, False)
    assert await gazetteer.search_places('galway') == [], 'searches are answered, from what is there'
    await gazetteer.stop()


@pytest.mark.asyncio(loop_scope="session")
async def test_searches_are_bounded_and_never_logged(places, caplog, monkeypatch):
    gazetteer = await started(places)
    caplog.set_level(logging.DEBUG)
    await gazetteer.search_places('Galway secretfarm')
    with pytest.raises(IllegalOperationError, match='west, south, east, north'):
        await gazetteer.search_places('secretfarm', viewbox=[1, 2])

    monkeypatch.setattr(index_module, 'SEARCH_SECONDS', -1)
    monkeypatch.setattr(index_module, 'PROGRESS_STEPS', 1)
    with pytest.raises(IllegalOperationError, match='took too long'):
        await gazetteer.search_places('secretfarm')
    monkeypatch.undo()

    monkeypatch.setattr(gazetteer_module, 'SEARCH_WAIT_SECONDS', 0.1)
    gazetteer._searching = asyncio.Semaphore(0)  # as many under way as are let run at once
    with pytest.raises(IllegalOperationError, match='busy'):
        await gazetteer.search_places('secretfarm')
    assert not [record for record in caplog.records if 'secretfarm' in record.getMessage()]
    await gazetteer.stop()
