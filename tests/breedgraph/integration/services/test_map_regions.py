"""
The map regions service (adapters/pmtiles/map_regions.py) with the real state store, a fake pmtiles command that
writes small files, and local outlines: squares, so no requests leave the test. Each test runs twice: with the API
fetching itself, and with the map worker (src/map_worker) fetching for it (adapters/pmtiles/jobs.py), run here with a
client calling the state store and what the API's routes call.
"""
import asyncio
import importlib.util
import json
import sys
from pathlib import Path
from types import SimpleNamespace

import pytest
import pytest_asyncio

from breedgraph.adapters.pmtiles import PmtilesMapRegions
from breedgraph.adapters.pmtiles import map_regions as map_regions_module
from breedgraph.adapters.pmtiles.regions import Region
from breedgraph.service_layer.infrastructure.map_regions import MapState, MapSectionStatus
from breedgraph.adapters.pmtiles.jobs import (
    receive_result, receive_extract, sources, LeaseNotHeld, BadUpload, NoSpace, MapRegionError
)
from map_worker.adapters.cache import ExtractCache
from map_worker.adapters.http.abstract_client import AbstractMapAPIClient, UploadRefused
from map_worker.domain.job import MapJob
from map_worker.fetching import PmtilesCommand
from map_worker.service_layer import handlers as handlers_module
from map_worker.service_layer.handlers import MapHandlers
from map_worker.service_layer.worker import MapWorker

BUILD = 'https://build.protomaps.com/20261026.pmtiles'
LEASE_SECONDS = 1.5

# The outline's file is named after its region: the API's own (USA-ADM0, USA-ADM1-a), or the map worker's (size-USA,
# extract-USA-ADM1-a), whose countries are named by code alone
NAME = """
def name(path):
    stem = Path(path).stem.removeprefix('size-').removeprefix('extract-')
    return f'{stem}-ADM0' if len(stem) == 3 else stem
"""

FAKE_PMTILES = """#!{python}
# Prints the configured size of a region on a dry run, else writes the output file and waits the configured seconds
import json, sys, time
from pathlib import Path
{name}
config = json.loads(Path({config!r}).read_text())
arguments = sys.argv[1:]
with open({log!r}, 'a') as log:
    log.write(json.dumps(arguments) + '\\n')
regions = [a.split('=', 1)[1] for a in arguments if a.startswith('--region=')]
region = name(regions[0]) if regions else 'world'
if '--dry-run' in arguments:
    print(f"extract.go:612: Extract transferred 1 MB (overfetch 0.05) for an archive size of {{config['sizes'][region]}}")
else:
    Path(arguments[2]).write_bytes(b'PMTiles')
    time.sleep(config['seconds'])
"""
exec(NAME)

SIZES = {
    'world': '560 MB',
    'LUX-ADM0': '300 MB',
    'USA-ADM0': '17 GB',  # over the 2 GB cap, so divided
    'USA-ADM1-a': '1 GB',
    'USA-ADM1-b': '3 GB',  # over the cap, so its ADM2 units are fetched
    'USA-ADM2-b1': '1.5 GB',
    'USA-ADM2-b2': '2.5 GB',  # too large even so
}


def square(west: float, south: float, east: float, north: float) -> dict:
    return {'type': 'Polygon', 'coordinates': [[[west, south], [east, south], [east, north], [west, north], [west, south]]]}


def outlines(*units) -> dict:
    return {'type': 'FeatureCollection', 'features': [
        {'type': 'Feature', 'properties': {'shapeID': shape_id, 'shapeName': name}, 'geometry': geometry}
        for shape_id, name, geometry in units
    ]}


OUTLINES = {
    'LUX-ADM0': outlines(('lux', 'Luxembourg', square(5.7, 49.4, 6.6, 50.2))),
    'USA-ADM0': outlines(('usa', 'United States', square(-100, 30, -80, 40))),
    'USA-ADM1': outlines(('a', 'Alpha', square(-100, 30, -90, 40)), ('b', 'Beta', square(-90, 30, -80, 40))),
    'USA-ADM2': outlines(
        ('a1', 'Alpha One', square(-100, 30, -90, 40)),
        ('b1', 'Beta One', square(-90, 30, -85, 40)),
        ('b2', 'Beta Two', square(-85, 30, -80, 40))
    ),
}

IN_A, ALSO_IN_A, IN_B1, IN_B2, IN_LUX = (35, -95), (36, -96), (35, -87), (35, -82), (49.6, 6.1)


class InProcessClient(AbstractMapAPIClient):
    """The map worker's client, calling what the API's routes call (entrypoints/fastapi/map_jobs.py)"""

    def __init__(self, maps: 'Maps'):
        self.maps = maps
        self.payloads = []

    async def lease(self, lane):
        leased = await self.maps.state_store.lease_map_job(lane, LEASE_SECONDS)
        if leased is None:
            return None
        kind, key, lease, payload = leased
        self.payloads.append((kind, key, payload))
        return MapJob(kind, key, lease, LEASE_SECONDS, payload)

    async def renew(self, job):
        return await self.maps.state_store.renew_map_job(job.kind, job.key, job.lease, LEASE_SECONDS)

    async def post_result(self, job, result):
        try:
            await receive_result(
                self.maps.state_store, self.maps.boundaries, LEASE_SECONDS, job.kind, job.key, job.lease, result
            )
        except LeaseNotHeld:
            return False
        return True

    async def post_failure(self, job, error):
        return await self.maps.state_store.finish_map_job(job.kind, job.key, job.lease, error=error)

    async def upload(self, job, extract):
        async def chunks():
            yield extract.path.read_bytes()
        try:
            await receive_extract(
                self.maps.state_store, self.maps.tiles, LEASE_SECONDS, job.key, job.lease,
                extract.path.stat().st_size, chunks(), build=extract.build, version=extract.version
            )
        except LeaseNotHeld:
            return False
        except (BadUpload, NoSpace) as e:
            raise UploadRefused(str(e))
        return True


class Maps:
    def __init__(self, path: Path, state_store, worker: bool = False):
        self.state_store = state_store
        self.worker = worker
        self.tiles = path / 'tiles'
        self.boundaries = path / 'boundaries'
        self.config = path / 'pmtiles.json'
        self.log = path / 'pmtiles.log'
        self.command = path / 'pmtiles'
        self.tiles.mkdir()
        self.boundaries.mkdir()
        (self.tiles / 'world.json').write_text(json.dumps({
            'url': 'world.pmtiles', 'maxZoom': 6, 'build': BUILD, 'version': '4.15.2'
        }))
        if not worker:
            # the map worker downloads them (fake_outlines)
            for name, content in OUTLINES.items():
                (self.boundaries / f'{name}.geojson').write_text(json.dumps(content))
        self.configure()
        self.command.write_text(FAKE_PMTILES.format(
            python=sys.executable, name=NAME, config=str(self.config), log=str(self.log)
        ))
        self.command.chmod(0o755)
        self.client = InProcessClient(self)
        self.work = path / 'work'
        self.cache = path / 'cache'
        self.map_worker: MapWorker | None = None
        self.running: asyncio.Task | None = None

    def start_worker(self, cache: bool = False):
        handlers = MapHandlers(
            PmtilesCommand(str(self.command)), self.work, '', '',
            cache=ExtractCache(self.cache, poll_seconds=0.05) if cache else None
        )
        handlers.clear()
        self.map_worker = MapWorker(self.client, handlers, poll_interval=0.05)
        self.running = asyncio.create_task(self.map_worker.run())

    async def stop_worker(self):
        if self.running is not None:
            await self.map_worker.shutdown()
            await asyncio.wait_for(self.running, 10)
            self.running = None

    def configure(self, seconds: float = 0):
        self.config.write_text(json.dumps({'sizes': SIZES, 'seconds': seconds}))

    def service(self, build: str = BUILD, max_tiles_gb: float = 0) -> PmtilesMapRegions:
        return PmtilesMapRegions(
            self.state_store, command=str(self.command), tiles_path=self.tiles,
            boundaries_path=self.boundaries, max_gb=2, build=build, poll_seconds=0.05, worker=self.worker,
            max_tiles_gb=max_tiles_gb
        )

    def extracts(self) -> list:
        """The regions extracted, by their outlines' names"""
        if not self.log.exists():
            return []
        calls = [json.loads(line) for line in self.log.read_text().splitlines()]
        return [
            name(next(a for a in call if a.startswith('--region=')).split('=', 1)[1])
            if any(a.startswith('--region=') for a in call) else 'world'
            for call in calls if '--dry-run' not in call
        ]

    def regions(self) -> list:
        """The files of the regions, those part way included"""
        return sorted(path.name for path in (self.tiles / 'regions').iterdir()) if (self.tiles / 'regions').exists() else []

    def layers(self) -> list:
        return [layer['url'] for layer in json.loads((self.tiles / 'tiles.json').read_text())['layers']]

    def countries(self) -> dict:
        """The extent to show each country by"""
        return json.loads((self.tiles / 'tiles.json').read_text())['countries']


async def state(regions: PmtilesMapRegions, code: str) -> tuple:
    """The state of the country's maps, and of its sections', as the location map is told them"""
    status = await regions.status(code)
    return status.state, [(section.name, section.state, section.error) for section in status.sections]


async def until(condition, seconds: float = 10):
    for _ in range(int(seconds / 0.05)):
        if condition():
            return
        await asyncio.sleep(0.05)
    raise TimeoutError("The condition was not met")


async def fake_outlines(url: str, code: str, level: str):
    """geoBoundaries' outlines as the map worker would download them"""
    if f'{code}-{level}' not in OUTLINES:
        raise MapRegionError(f"geoBoundaries has no {level} outlines for {code}")
    return {'boundaryLicense': 'CC BY 4.0'}, OUTLINES[f'{code}-{level}']


@pytest_asyncio.fixture(loop_scope="session", params=['api', 'worker'])
async def maps(request, tmp_path, state_store, monkeypatch) -> Maps:
    """
    Each test starts with no map state, keeping the countries read model for the names, and runs with the API fetching
    itself and with the map worker fetching for it
    """
    async def clear():
        async for key in state_store.connection.scan_iter(match='map:*'):
            await state_store.connection.delete(key)
    await clear()
    maps = Maps(tmp_path, state_store, worker=request.param == 'worker')
    if maps.worker:
        monkeypatch.setattr(handlers_module, 'download_outlines', fake_outlines)
        maps.start_worker()
    yield maps
    await maps.stop_worker()
    await clear()


@pytest.mark.asyncio(loop_scope="session")
async def test_a_small_country_is_fetched_whole(maps, state_store):
    regions = maps.service()
    await regions.start()
    assert await state(regions, 'LUX') == (MapState.NONE, [])
    await regions.request_country('LUX')
    await regions.wait_until_idle()

    assert maps.extracts() == ['LUX-ADM0']
    assert maps.regions() == ['LUX.json', 'LUX.pmtiles']
    sidecar = json.loads((maps.tiles / 'regions' / 'LUX.json').read_text())
    assert {key: sidecar[key] for key in ('name', 'level', 'minZoom', 'maxZoom', 'bounds', 'build', 'size')} == {
        'name': 'Luxembourg', 'level': 'ADM0', 'minZoom': 7, 'maxZoom': 15, 'bounds': [[49.4, 5.7], [50.2, 6.6]],
        'build': BUILD, 'size': 7
    }
    assert maps.layers() == ['world.pmtiles', 'regions/LUX.pmtiles']
    assert maps.countries() == {'LUX': {'name': 'Luxembourg', 'bounds': [[49.4, 5.7], [50.2, 6.6]]}}
    status = await regions.status('LUX')
    assert (status.state, status.size, status.limit, status.enabled) == (MapState.READY, 300 * 10 ** 6, 2 * 10 ** 9, True)
    assert await state_store.get_pending_map_regions() == []

    # placing a location in it fetches nothing more
    await regions.request_places('LUX', [IN_LUX])
    await regions.wait_until_idle()
    assert maps.extracts() == ['LUX-ADM0']
    await regions.stop()


@pytest.mark.asyncio(loop_scope="session")
async def test_a_large_country_is_divided_and_placed_locations_fetch_their_sections(maps, state_store):
    regions = maps.service()
    await regions.start()
    await regions.request_country('USA')
    await regions.wait_until_idle()
    assert maps.extracts() == []
    status = await regions.status('USA')
    assert (status.state, status.size, status.sections) == (MapState.DIVIDED, 17 * 10 ** 9, [])
    # a divided country is still shown by its outline
    assert maps.layers() == ['world.pmtiles']
    assert maps.countries() == {'USA': {'name': 'United States of America', 'bounds': [[30, -100], [40, -80]]}}

    await regions.request_places('USA', [IN_A])
    await regions.wait_until_idle()
    assert maps.extracts() == ['USA-ADM1-a']
    assert maps.layers() == ['world.pmtiles', 'regions/USA-ADM1-a.pmtiles']
    assert (await regions.status('USA')).sections == [MapSectionStatus('Alpha', MapState.READY, 10 ** 9)]

    # another location in the same section fetches nothing more
    await regions.request_places('USA', [ALSO_IN_A])
    await regions.wait_until_idle()
    assert maps.extracts() == ['USA-ADM1-a']

    # a section over the cap is fetched by its ADM2 unit, and one too large even so fails
    await regions.request_places('USA', [IN_B1, IN_B2])
    await regions.wait_until_idle()
    assert maps.extracts() == ['USA-ADM1-a', 'USA-ADM2-b1']
    assert await state(regions, 'USA') == (MapState.DIVIDED, [
        ('Alpha', MapState.READY, None),
        ('Beta One', MapState.READY, None),
        ('Beta Two', MapState.FAILED,
         "they would take 2.5 GB, more than this site's limit of 2.0 GB, even for the smallest region holding the location")
    ])
    assert await state_store.get_pending_map_regions() == []
    await regions.stop()


@pytest.mark.asyncio(loop_scope="session")
async def test_placing_a_location_in_a_country_never_requested_requests_it(maps):
    """As for countries added before maps were fetched"""
    regions = maps.service()
    await regions.start()
    await regions.request_places('USA', [IN_A])
    await regions.request_places('LUX', [IN_LUX])
    await regions.wait_until_idle()
    assert sorted(maps.extracts()) == ['LUX-ADM0', 'USA-ADM1-a']
    assert await state(regions, 'USA') == (MapState.DIVIDED, [('Alpha', MapState.READY, None)])
    assert await state(regions, 'LUX') == (MapState.READY, [])
    await regions.stop()


@pytest.mark.asyncio(loop_scope="session")
async def test_two_requests_for_a_region_give_one_extract_which_both_show_as_fetching(maps):
    """Two processes, sharing the state store"""
    maps.configure(seconds=1)
    first, second = maps.service(), maps.service()
    await first.start()
    await second.start()
    await first.request_country('LUX')
    await until(lambda: maps.extracts())  # under way
    await second.request_country('LUX')
    assert await state(second, 'LUX') == (MapState.FETCHING, [])
    await first.wait_until_idle()
    await second.wait_until_idle()

    assert maps.extracts() == ['LUX-ADM0']
    assert await state(second, 'LUX') == (MapState.READY, [])
    await first.stop()
    await second.stop()


@pytest.mark.asyncio(loop_scope="session")
async def test_removing_a_country_deletes_its_regions(maps, state_store):
    regions = maps.service()
    await regions.start()
    await regions.request_country('LUX')
    await regions.request_country('USA')
    await regions.wait_until_idle()
    await regions.request_places('USA', [IN_A, IN_B1])
    await regions.wait_until_idle()
    assert len(maps.regions()) == 6

    await regions.remove_country('USA')
    assert maps.regions() == ['LUX.json', 'LUX.pmtiles']
    assert maps.layers() == ['world.pmtiles', 'regions/LUX.pmtiles']
    assert list(maps.countries()) == ['LUX']
    assert await state_store.get_map_region_size('USA') is None
    assert await state_store.get_map_region_size('USA-ADM1-a') is None
    assert await state_store.get_map_region_size('LUX') is not None
    assert not list(maps.boundaries.glob('USA-ADM?-*.geojson'))
    assert await state(regions, 'USA') == (MapState.NONE, [])

    # and one removed while it is fetched is stopped, leaving nothing behind
    maps.configure(seconds=30)
    await regions.request_country('USA')
    await regions.wait_until_idle()
    await regions.request_places('USA', [IN_A])
    await until(lambda: 'USA-ADM1-a' in maps.extracts()[-1:] and len(maps.extracts()) == 4)
    assert await state(regions, 'USA') == (MapState.DIVIDED, [('Alpha', MapState.FETCHING, None)])
    await regions.remove_country('USA')
    await regions.wait_until_idle()
    assert maps.regions() == ['LUX.json', 'LUX.pmtiles']
    assert await state(regions, 'USA') == (MapState.NONE, [])
    assert await state_store.get_pending_map_regions() == []
    await regions.stop()


@pytest.mark.asyncio(loop_scope="session")
async def test_an_interrupted_fetch_resumes_at_start(maps, state_store):
    if maps.worker:
        pytest.skip("the map worker goes on with the extract: test_a_restart_joins_the_map_workers_extract")
    maps.configure(seconds=30)
    regions = maps.service()
    await regions.start()
    await regions.request_country('LUX')
    await until(lambda: maps.extracts())
    await regions.stop()
    assert maps.regions() == ['.LUX.pmtiles.partial']
    assert await state_store.get_pending_map_regions() == ['LUX']

    maps.configure(seconds=0)
    restarted = maps.service()
    await restarted.start()
    await restarted.wait_until_idle()
    assert maps.extracts() == ['LUX-ADM0', 'LUX-ADM0']
    assert maps.regions() == ['LUX.json', 'LUX.pmtiles']
    assert await state(restarted, 'LUX') == (MapState.READY, [])
    await restarted.stop()


@pytest.mark.asyncio(loop_scope="session")
async def test_a_fetch_without_enough_disk_space_fails(maps, state_store, monkeypatch):
    # 300 MB needs 330 MB and 1 GB more
    monkeypatch.setattr(map_regions_module.shutil, 'disk_usage', lambda path: SimpleNamespace(free=1_300_000_000))
    regions = maps.service()
    await regions.start()
    await regions.request_country('LUX')
    await regions.wait_until_idle()
    assert maps.extracts() == []
    assert maps.regions() == []
    assert await state(regions, 'LUX') == (MapState.FAILED, [])
    assert (await regions.status('LUX')).error == "the server has too little disk space for them, which would take 0.3 GB"
    assert await state_store.get_pending_map_regions() == []
    await regions.stop()


@pytest.mark.asyncio(loop_scope="session")
async def test_a_fetch_that_would_pass_the_map_storage_cap_fails(maps, state_store):
    """As on the demonstration site, which shares production's disk"""
    regions = maps.service(max_tiles_gb=0.31)
    await regions.start()
    await regions.request_country('LUX')  # 300 MB
    await regions.request_country('USA')  # divided, so nothing yet
    await regions.wait_until_idle()
    assert maps.regions() == ['LUX.json', 'LUX.pmtiles']

    await regions.request_places('USA', [IN_A])  # 1 GB more
    await regions.wait_until_idle()
    assert maps.extracts() == ['LUX-ADM0']
    assert maps.regions() == ['LUX.json', 'LUX.pmtiles']
    assert await state(regions, 'USA') == (MapState.DIVIDED, [(
        'Alpha', MapState.FAILED,
        "this site's storage for detailed maps is full: they would take 1.0 GB, and the maps it holds take 0.0 GB of the "
        "0.3 GB allowed"
    )])

    # a region fetched again replaces its own file, which is not counted
    assert await regions.fetch_now(Region('LUX'), refresh=True) is map_regions_module.Outcome.READY

    # asked for again once there is room, the section's failure is forgotten
    regions.max_tiles_bytes = 0
    await regions.request_places('USA', [IN_A])
    await regions.wait_until_idle()
    assert await state(regions, 'USA') == (MapState.DIVIDED, [('Alpha', MapState.READY, None)])
    await regions.stop()


@pytest.mark.asyncio(loop_scope="session")
async def test_nothing_is_fetched_without_the_pmtiles_command(maps, state_store):
    regions = PmtilesMapRegions(state_store, command='', tiles_path=maps.tiles, boundaries_path=maps.boundaries)
    await regions.start()
    await regions.request_country('LUX')
    await regions.request_places('USA', [IN_A])
    await regions.wait_until_idle()
    assert maps.extracts() == []
    assert await state_store.get_pending_map_regions() == []
    status = await regions.status('LUX')
    assert (status.state, status.enabled) == (MapState.NONE, False)


""" With the map worker """


@pytest.mark.asyncio(loop_scope="session")
async def test_a_restart_joins_the_map_workers_extract(maps, state_store):
    """The API stops while the worker extracts: restarted, it waits for that extract rather than asking again"""
    if not maps.worker:
        pytest.skip("the API's own extract stops with it: test_an_interrupted_fetch_resumes_at_start")
    maps.configure(seconds=1)
    regions = maps.service()
    await regions.start()
    await regions.request_country('LUX')
    await until(lambda: maps.extracts())
    await regions.stop()
    assert await state_store.get_pending_map_regions() == ['LUX']

    restarted = maps.service()
    await restarted.start()
    await restarted.wait_until_idle()
    assert maps.extracts() == ['LUX-ADM0']
    assert maps.regions() == ['LUX.json', 'LUX.pmtiles']
    assert await state(restarted, 'LUX') == (MapState.READY, [])
    assert await state_store.get_map_job('extract', 'LUX') is None, 'its file taken, the job is gone'
    await restarted.stop()


@pytest.mark.asyncio(loop_scope="session")
async def test_without_a_map_worker_regions_wait(maps, state_store):
    if not maps.worker:
        pytest.skip("only the map worker's jobs wait for it")
    await maps.stop_worker()
    regions = maps.service()
    await regions.start()
    await regions.request_country('LUX')
    await asyncio.sleep(0.3)
    assert await state_store.get_pending_map_regions() == ['LUX']
    assert (await state_store.get_map_job('outlines', 'LUX-ADM0'))['state'] == 'queued'
    assert await state(regions, 'LUX') == (MapState.PENDING, [])

    # the worker started, the region is fetched
    maps.start_worker()
    await regions.wait_until_idle()
    assert maps.regions() == ['LUX.json', 'LUX.pmtiles']
    await regions.stop()


@pytest.mark.asyncio(loop_scope="session")
async def test_the_map_worker_is_sent_outlines_but_no_coordinates(maps):
    if not maps.worker:
        pytest.skip("only the map worker is sent jobs")
    regions = maps.service()
    await regions.start()
    await regions.request_country('USA')
    await regions.wait_until_idle()
    await regions.request_places('USA', [IN_A, IN_B1])
    await regions.wait_until_idle()
    await regions.stop()

    jobs = maps.client.payloads
    assert {kind for kind, _, _ in jobs} == {'outlines', 'size', 'extract'}
    for kind, key, payload in jobs:
        if kind == 'outlines':
            assert payload == {'code': key[:3], 'level': key[4:]}
        elif kind == 'size':
            assert set(payload) == {'outline', 'build', 'minzoom', 'maxzoom'}
        else:
            assert set(payload) == {'outline', 'build', 'minzoom', 'maxzoom', 'version', 'fresh'}
            assert payload['outline']['type'] == 'FeatureCollection'
    # a section is sent as its own outline alone, as the API keeps it
    section = next(payload for kind, key, payload in jobs if (kind, key) == ('extract', 'USA-ADM1-a'))
    assert section['outline'] == json.loads((maps.boundaries / 'USA-ADM1-a.geojson').read_text())
    assert json.loads((maps.boundaries / 'USA-ADM1.json').read_text()) == {'boundaryLicense': 'CC BY 4.0'}


@pytest.mark.asyncio(loop_scope="session")
async def test_the_map_worker_lists_the_builds(maps, monkeypatch):
    """Regions are cut from the newest build of the world file's version (4), as the map worker lists them"""
    if not maps.worker:
        pytest.skip("only the map worker is sent jobs")

    async def builds(url):
        return [
            {'key': '20261025.pmtiles', 'version': '4.14.0'},
            {'key': '20261026.pmtiles', 'version': '4.15.2'},
            {'key': '20261027.pmtiles', 'version': '5.0.0'},
        ]
    monkeypatch.setattr(handlers_module, 'list_builds', builds)
    regions = maps.service(build='latest')
    await regions.start()
    await regions.request_country('LUX')
    await regions.wait_until_idle()
    await regions.stop()
    sidecar = json.loads((maps.tiles / 'regions' / 'LUX.json').read_text())
    assert (sidecar['build'], sidecar['version']) == ('https://build.protomaps.com/20261026.pmtiles', '4.15.2')
    assert ('builds', 'latest', {}) in maps.client.payloads


@pytest.mark.asyncio(loop_scope="session")
async def test_a_country_added_again_is_sent_from_the_map_workers_cache(maps, monkeypatch):
    """Removed and added again (or added on another site whose worker shares the cache), it is not cut again"""
    if not maps.worker:
        pytest.skip("only the map worker keeps what it cuts")
    builds = [{'key': '20261026.pmtiles', 'version': '4.15.2'}]

    async def list_builds(url):
        return builds
    monkeypatch.setattr(handlers_module, 'list_builds', list_builds)
    await maps.stop_worker()
    maps.start_worker(cache=True)

    regions = maps.service(build='latest')
    await regions.start()
    await regions.request_country('LUX')
    await regions.wait_until_idle()
    await regions.remove_country('LUX')
    await regions.stop()
    assert maps.regions() == []

    # a day later, from a newer build of the same version
    builds.append({'key': '20261027.pmtiles', 'version': '4.16.0'})
    again = maps.service(build='latest')
    await again.start()
    await again.request_country('LUX')
    await again.wait_until_idle()
    assert maps.extracts() == ['LUX-ADM0']
    assert maps.regions() == ['LUX.json', 'LUX.pmtiles']
    sidecar = json.loads((maps.tiles / 'regions' / 'LUX.json').read_text())
    assert (sidecar['build'], sidecar['version']) == (BUILD, '4.15.2'), 'the build it was cut from'

    # refreshed, it is cut again from the newest
    assert await again.fetch_now(Region('LUX'), refresh=True) is map_regions_module.Outcome.READY
    await again.stop()
    assert maps.extracts() == ['LUX-ADM0', 'LUX-ADM0']
    sidecar = json.loads((maps.tiles / 'regions' / 'LUX.json').read_text())
    assert (sidecar['build'], sidecar['version']) == ('https://build.protomaps.com/20261027.pmtiles', '4.16.0')


@pytest.mark.asyncio(loop_scope="session")
async def test_a_second_sites_world_file_is_sent_from_the_map_workers_cache(maps, state_store, monkeypatch):
    """As for the demonstration site, whose world file is its own (scripts/map_tiles.py), unless asked for fresh"""
    if not maps.worker:
        pytest.skip("only the map worker keeps what it cuts")
    script = Path(__file__).parents[4] / 'scripts' / 'map_tiles.py'
    spec = importlib.util.spec_from_file_location('map_tiles', script)
    map_tiles = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(map_tiles)
    builds = [{'key': '20261026.pmtiles', 'version': '4.15.2'}]

    async def list_builds(url):
        return builds
    monkeypatch.setattr(handlers_module, 'list_builds', list_builds)
    await maps.stop_worker()
    maps.start_worker(cache=True)

    async def cut(fresh: bool = False) -> dict:
        pmtiles, protomaps, _ = sources(state_store, True, '', 'latest', maps.boundaries, poll_seconds=0.05)
        args = SimpleNamespace(dry_run=False, world_maxzoom=6, fresh=fresh)
        assert await map_tiles.cut_world(args, maps.tiles, pmtiles, protomaps) == 0
        return json.loads((maps.tiles / 'world.json').read_text())

    assert (await cut())['build'] == BUILD
    builds.append({'key': '20261027.pmtiles', 'version': '4.16.0'})
    world = await cut()
    assert maps.extracts() == ['world'], 'sent from the cache'
    assert (world['build'], world['version']) == (BUILD, '4.15.2'), 'the build it was cut from'
    assert (maps.tiles / 'world.pmtiles').read_bytes() == b'PMTiles'

    world = await cut(fresh=True)
    assert maps.extracts() == ['world', 'world']
    assert (world['build'], world['version']) == ('https://build.protomaps.com/20261027.pmtiles', '4.16.0')
