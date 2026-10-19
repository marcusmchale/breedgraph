"""
The map regions service (adapters/pmtiles/map_regions.py) with the real state store, a fake pmtiles command that
writes small files, and local outlines: squares, so no requests leave the test.
"""
import asyncio
import json
import sys
from pathlib import Path
from types import SimpleNamespace

import pytest
import pytest_asyncio

from breedgraph.adapters.pmtiles import PmtilesMapRegions
from breedgraph.adapters.pmtiles import map_regions as map_regions_module

BUILD = 'https://example.org/build.pmtiles'

FAKE_PMTILES = """#!{python}
# Prints the configured size of a region on a dry run, else writes the output file and waits the configured seconds
import json, sys, time
from pathlib import Path
config = json.loads(Path({config!r}).read_text())
arguments = sys.argv[1:]
with open({log!r}, 'a') as log:
    log.write(json.dumps(arguments) + '\\n')
region = Path(next(a for a in arguments if a.startswith('--region=')).split('=', 1)[1]).stem
if '--dry-run' in arguments:
    print(f"extract.go:612: Extract transferred 1 MB (overfetch 0.05) for an archive size of {{config['sizes'][region]}}")
else:
    Path(arguments[2]).write_bytes(b'tiles')
    time.sleep(config['seconds'])
"""

SIZES = {
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


class Maps:
    def __init__(self, path: Path, state_store):
        self.state_store = state_store
        self.tiles = path / 'tiles'
        self.boundaries = path / 'boundaries'
        self.config = path / 'pmtiles.json'
        self.log = path / 'pmtiles.log'
        self.command = path / 'pmtiles'
        self.events = []
        self.tiles.mkdir()
        self.boundaries.mkdir()
        (self.tiles / 'world.json').write_text(json.dumps({
            'url': 'world.pmtiles', 'maxZoom': 6, 'build': BUILD, 'version': '4.15.2'
        }))
        for name, content in OUTLINES.items():
            (self.boundaries / f'{name}.geojson').write_text(json.dumps(content))
        self.configure()
        self.command.write_text(FAKE_PMTILES.format(python=sys.executable, config=str(self.config), log=str(self.log)))
        self.command.chmod(0o755)

    def configure(self, seconds: float = 0):
        self.config.write_text(json.dumps({'sizes': SIZES, 'seconds': seconds}))

    def service(self) -> PmtilesMapRegions:
        async def publish(event):
            self.events.append(event)
        return PmtilesMapRegions(
            self.state_store, publish=publish, command=str(self.command), tiles_path=self.tiles,
            boundaries_path=self.boundaries, max_gb=2, build=BUILD, poll_seconds=0.05
        )

    def extracts(self) -> list:
        """The regions extracted, by their outlines' names"""
        if not self.log.exists():
            return []
        calls = [json.loads(line) for line in self.log.read_text().splitlines()]
        return [
            Path(next(a for a in call if a.startswith('--region=')).split('=', 1)[1]).stem
            for call in calls if '--dry-run' not in call
        ]

    def sent(self) -> list:
        return [(type(event).__name__, event.name, event.user_ids) for event in self.events]

    def regions(self) -> list:
        return sorted(path.name for path in (self.tiles / 'regions').iterdir()) if (self.tiles / 'regions').exists() else []

    def layers(self) -> list:
        return [layer['url'] for layer in json.loads((self.tiles / 'tiles.json').read_text())['layers']]


async def until(condition, seconds: float = 10):
    for _ in range(int(seconds / 0.05)):
        if condition():
            return
        await asyncio.sleep(0.05)
    raise TimeoutError("The condition was not met")


@pytest_asyncio.fixture(loop_scope="session")
async def maps(tmp_path, state_store) -> Maps:
    """Each test starts with no map state, keeping the countries read model for the names"""
    async def clear():
        async for key in state_store.connection.scan_iter(match='map:*'):
            await state_store.connection.delete(key)
    await clear()
    yield Maps(tmp_path, state_store)
    await clear()


@pytest.mark.asyncio(loop_scope="session")
async def test_a_small_country_is_fetched_whole(maps, state_store):
    regions = maps.service()
    await regions.start()
    await regions.request_country('LUX', requested_by=7)
    await regions.wait_until_idle()

    assert maps.extracts() == ['LUX-ADM0']
    assert maps.regions() == ['LUX.json', 'LUX.pmtiles']
    sidecar = json.loads((maps.tiles / 'regions' / 'LUX.json').read_text())
    assert {key: sidecar[key] for key in ('name', 'level', 'minZoom', 'maxZoom', 'bounds', 'build', 'size')} == {
        'name': 'Luxembourg', 'level': 'ADM0', 'minZoom': 7, 'maxZoom': 15, 'bounds': [[49.4, 5.7], [50.2, 6.6]],
        'build': BUILD, 'size': 5
    }
    assert maps.layers() == ['world.pmtiles', 'regions/LUX.pmtiles']
    assert maps.sent() == [('MapRegionFetching', 'Luxembourg', [7]), ('MapRegionReady', 'Luxembourg', [7])]
    assert await state_store.get_pending_map_regions() == []

    # placing a location in it fetches nothing more
    await regions.request_places('LUX', [IN_LUX], requested_by=8)
    await regions.wait_until_idle()
    assert maps.extracts() == ['LUX-ADM0'] and len(maps.events) == 2
    await regions.stop()


@pytest.mark.asyncio(loop_scope="session")
async def test_a_large_country_is_divided_and_placed_locations_fetch_their_sections(maps, state_store):
    regions = maps.service()
    await regions.start()
    await regions.request_country('USA', requested_by=7)
    await regions.wait_until_idle()
    assert maps.extracts() == []
    assert maps.sent() == [('MapCountryDivided', 'United States of America', [7])]

    await regions.request_places('USA', [IN_A], requested_by=8)
    await regions.wait_until_idle()
    assert maps.extracts() == ['USA-ADM1-a']
    assert maps.layers() == ['world.pmtiles', 'regions/USA-ADM1-a.pmtiles']
    assert maps.sent()[1:] == [
        ('MapRegionFetching', 'Alpha (United States of America)', [8]),
        ('MapRegionReady', 'Alpha (United States of America)', [8])
    ]

    # another location in the same section fetches nothing more
    await regions.request_places('USA', [ALSO_IN_A], requested_by=9)
    await regions.wait_until_idle()
    assert maps.extracts() == ['USA-ADM1-a'] and len(maps.events) == 3

    # a section over the cap is fetched by its ADM2 unit, and one too large even so fails
    await regions.request_places('USA', [IN_B1, IN_B2], requested_by=9)
    await regions.wait_until_idle()
    assert maps.extracts() == ['USA-ADM1-a', 'USA-ADM2-b1']
    assert sorted(maps.sent()[3:]) == [
        ('MapRegionFailed', 'Beta Two (United States of America)', [9]),
        ('MapRegionFetching', 'Beta One (United States of America)', [9]),
        ('MapRegionReady', 'Beta One (United States of America)', [9])
    ]
    assert await state_store.get_pending_map_regions() == []
    await regions.stop()


@pytest.mark.asyncio(loop_scope="session")
async def test_placing_a_location_in_a_country_never_requested_requests_it(maps):
    """As for countries added before maps were fetched"""
    regions = maps.service()
    await regions.start()
    await regions.request_places('USA', [IN_A], requested_by=8)
    await regions.request_places('LUX', [IN_LUX], requested_by=8)
    await regions.wait_until_idle()
    assert sorted(maps.extracts()) == ['LUX-ADM0', 'USA-ADM1-a']
    assert sorted(maps.sent()) == [
        ('MapCountryDivided', 'United States of America', [8]),
        ('MapRegionFetching', 'Alpha (United States of America)', [8]),
        ('MapRegionFetching', 'Luxembourg', [8]),
        ('MapRegionReady', 'Alpha (United States of America)', [8]),
        ('MapRegionReady', 'Luxembourg', [8])
    ]
    await regions.stop()


@pytest.mark.asyncio(loop_scope="session")
async def test_two_requests_for_a_region_give_one_extract_and_both_requestors_hear(maps):
    """Two processes, sharing the state store"""
    maps.configure(seconds=1)
    first, second = maps.service(), maps.service()
    await first.start()
    await second.start()
    await first.request_country('LUX', requested_by=7)
    await until(lambda: maps.extracts())  # under way
    await second.request_country('LUX', requested_by=8)
    await first.wait_until_idle()
    await second.wait_until_idle()

    assert maps.extracts() == ['LUX-ADM0']
    assert sorted(maps.sent()) == [
        ('MapRegionFetching', 'Luxembourg', [7]),
        ('MapRegionFetching', 'Luxembourg', [8]),
        ('MapRegionReady', 'Luxembourg', [7, 8])
    ]
    await first.stop()
    await second.stop()


@pytest.mark.asyncio(loop_scope="session")
async def test_removing_a_country_deletes_its_regions(maps, state_store):
    regions = maps.service()
    await regions.start()
    await regions.request_country('LUX', requested_by=7)
    await regions.request_country('USA', requested_by=7)
    await regions.wait_until_idle()
    await regions.request_places('USA', [IN_A, IN_B1], requested_by=7)
    await regions.wait_until_idle()
    assert len(maps.regions()) == 6

    await regions.remove_country('USA')
    assert maps.regions() == ['LUX.json', 'LUX.pmtiles']
    assert maps.layers() == ['world.pmtiles', 'regions/LUX.pmtiles']
    assert await state_store.get_map_region_size('USA') is None
    assert await state_store.get_map_region_size('USA-ADM1-a') is None
    assert await state_store.get_map_region_size('LUX') is not None
    assert not list(maps.boundaries.glob('USA-ADM?-*.geojson'))

    # and one removed while it is fetched is stopped, leaving nothing behind and telling no one it is ready
    maps.configure(seconds=30)
    maps.events.clear()
    await regions.request_country('USA', requested_by=7)
    await regions.wait_until_idle()
    await regions.request_places('USA', [IN_A], requested_by=8)
    await until(lambda: 'USA-ADM1-a' in maps.extracts()[-1:] and len(maps.extracts()) == 4)
    await regions.remove_country('USA')
    await regions.wait_until_idle()
    assert maps.regions() == ['LUX.json', 'LUX.pmtiles']
    assert [name for name, *_ in maps.sent()] == ['MapCountryDivided', 'MapRegionFetching']
    assert await state_store.get_pending_map_regions() == []
    await regions.stop()


@pytest.mark.asyncio(loop_scope="session")
async def test_an_interrupted_fetch_resumes_at_start(maps, state_store):
    maps.configure(seconds=30)
    regions = maps.service()
    await regions.start()
    await regions.request_country('LUX', requested_by=7)
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
    # told once that it was being fetched
    assert maps.sent() == [('MapRegionFetching', 'Luxembourg', [7]), ('MapRegionReady', 'Luxembourg', [7])]
    await restarted.stop()


@pytest.mark.asyncio(loop_scope="session")
async def test_a_fetch_without_enough_disk_space_fails(maps, state_store, monkeypatch):
    # 300 MB needs 330 MB and 1 GB more
    monkeypatch.setattr(map_regions_module.shutil, 'disk_usage', lambda path: SimpleNamespace(free=1_300_000_000))
    regions = maps.service()
    await regions.start()
    await regions.request_country('LUX', requested_by=7)
    await regions.wait_until_idle()
    assert maps.extracts() == []
    assert maps.regions() == []
    assert maps.sent() == [('MapRegionFailed', 'Luxembourg', [7])]
    assert await state_store.get_pending_map_regions() == []
    await regions.stop()


@pytest.mark.asyncio(loop_scope="session")
async def test_nothing_is_fetched_without_the_pmtiles_command(maps, state_store):
    regions = PmtilesMapRegions(state_store, command='', tiles_path=maps.tiles, boundaries_path=maps.boundaries)
    await regions.start()
    await regions.request_country('LUX', requested_by=7)
    await regions.request_places('USA', [IN_A], requested_by=7)
    await regions.wait_until_idle()
    assert maps.extracts() == [] and maps.events == []
    assert await state_store.get_pending_map_regions() == []
