import json

import pytest

from breedgraph.adapters.pmtiles.command import parse_archive_size, latest_build, MapRegionError
from breedgraph.adapters.pmtiles.regions import (
    Region, contains, section_for, geometry_bounds, features_bounds, country_bounds, write_tiles_json, read_sidecars
)


def square(west: float, south: float, east: float, north: float) -> list:
    return [[west, south], [east, south], [east, north], [west, north], [west, south]]


def feature(shape_id: str, *polygons: list, kind: str = 'Polygon') -> dict:
    geometry = {'type': kind, 'coordinates': polygons[0] if kind == 'Polygon' else list(polygons)}
    return {'type': 'Feature', 'properties': {'shapeID': shape_id, 'shapeName': shape_id}, 'geometry': geometry}


# Two sections side by side, the western one with a hole, and an island in two parts
WEST = feature('west', [square(0, 0, 10, 10), square(4, 4, 6, 6)])
EAST = feature('east', [square(10, 0, 20, 10)])
ISLAND = feature('island', [square(30, 0, 31, 1)], [square(32, 0, 33, 1)], kind='MultiPolygon')


def test_region_keys():
    assert Region('IRL').key == 'IRL'
    assert Region('USA', 'ADM1', '66186276B69138566591314').key == 'USA-ADM1-66186276B69138566591314'
    for key in ('IRL', 'USA-ADM1-66186276B69138566591314', 'USA-ADM2-a-b_c'):
        assert Region.from_key(key).key == key
    assert Region.from_key('USA-ADM2-a-b_c').shape_id == 'a-b_c'


@pytest.mark.parametrize('code, level, shape_id', [
    ('irl', 'ADM0', None),
    ('IRL', 'ADM0', 'id'),
    ('USA', 'ADM3', 'id'),
    ('USA', 'ADM1', None),
    ('USA', 'ADM1', '../world'),
])
def test_region_keys_are_checked(code, level, shape_id):
    """Keys name files, so nothing else gets through"""
    with pytest.raises(ValueError):
        Region(code, level, shape_id)


def test_points_in_polygons():
    # (latitude, longitude)
    assert contains(WEST['geometry'], (1, 1))
    assert not contains(WEST['geometry'], (5, 5))  # in the hole
    assert not contains(WEST['geometry'], (1, 11))
    assert contains(ISLAND['geometry'], (0.5, 32.5))
    assert not contains(ISLAND['geometry'], (0.5, 31.5))


def test_the_section_holding_a_point():
    assert section_for([WEST, EAST, ISLAND], (5, 15)) is EAST
    assert section_for([WEST, EAST, ISLAND], (0.5, 30.5)) is ISLAND


def test_a_point_outside_every_outline_takes_the_nearest_section():
    # just off the east coast, and in the western hole, which here belongs to neither
    assert section_for([WEST, EAST], (5, 20.5)) is EAST
    assert section_for([WEST, EAST], (5, 5.5)) is WEST
    # but not one far from all of them
    assert section_for([WEST, EAST], (50, 50)) is None
    assert section_for([], (5, 5)) is None


def test_bounds():
    assert geometry_bounds(WEST['geometry']) == [[0, 0], [10, 10]]
    assert features_bounds([WEST, EAST, ISLAND]) == [[0, 0], [10, 33]]
    assert features_bounds([]) is None


def test_a_country_is_shown_by_its_main_parts():
    mainland = feature('mainland', [square(0, 40, 10, 50)])
    island = feature('island', [square(10.5, 41, 12, 43)])  # more than 1% of the mainland, nearby
    territory = feature('territory', [square(-60, 4, -59.5, 4.5)])  # less, across an ocean
    assert country_bounds([mainland, island, territory]) == [[40, 0], [50, 12]]
    assert features_bounds([mainland, island, territory]) == [[4, -60], [50, 12]]
    # a single small part is still shown
    assert country_bounds([territory]) == [[4, -60], [4.5, -59.5]]
    assert country_bounds([]) is None


def test_a_country_across_the_antimeridian_is_shown_across_it():
    """Its parts are split at 180 degrees; the narrower extent crosses it, with east above 180 as Leaflet takes it"""
    west_of = feature('west', [square(170, -20, 180, -10)])
    east_of = feature('east', [square(-180, -20, -175, -10)])
    assert country_bounds([west_of, east_of]) == [[-20, 170], [-10, 185]]
    assert country_bounds([feature('wide', [square(-170, 0, 170, 10)])]) == [[0, -170], [10, 170]]


@pytest.mark.parametrize('output, size', [
    ('extract.go:612: Extract transferred 476 MB (overfetch 0.05) for an archive size of 454 MB', 454_000_000),
    ('... for an archive size of 5.5 GB\n', 5_500_000_000),
    ('... for an archive size of 17 GB', 17_000_000_000),
    ('... for an archive size of 812 kB', 812_000),
    ('... for an archive size of 0 B', 0),
])
def test_dry_run_sizes(output, size):
    assert parse_archive_size(output) == size


def test_a_dry_run_without_a_size_fails():
    with pytest.raises(MapRegionError):
        parse_archive_size('extract.go:441: Region tiles 6020, result tile entries 6020')


def test_the_latest_build():
    builds = [
        {'key': '20261017.pmtiles', 'version': '4.15.1'},
        {'key': '20261019.pmtiles', 'version': '5.0.0'},
        {'key': '20261018.pmtiles', 'version': '4.15.2'},
        {'key': 'notes.txt', 'version': '4.15.2'},
    ]
    assert latest_build(builds)['key'] == '20261019.pmtiles'
    # of the world file's version, so the regions match it and the map's style
    assert latest_build(builds, major='4')['key'] == '20261018.pmtiles'
    assert latest_build(builds, major='3') is None


def write_region(tiles_path, key: str, name: str, complete: bool = True):
    regions = tiles_path / 'regions'
    regions.mkdir(parents=True, exist_ok=True)
    (regions / f'{key}.json').write_text(json.dumps({
        'key': key, 'url': f'regions/{key}.pmtiles', 'name': name, 'minZoom': 7, 'maxZoom': 15,
        'bounds': [[0, 0], [1, 1]], 'build': 'https://example.org/build.pmtiles', 'size': 1
    }))
    if complete:
        (regions / f'{key}.pmtiles').write_bytes(b'tiles')


def test_tiles_json_lists_the_world_and_the_complete_regions(tmp_path):
    assert not write_tiles_json(tmp_path)  # nothing without a world file
    assert not (tmp_path / 'tiles.json').exists()

    (tmp_path / 'world.json').write_text(json.dumps({
        'url': 'world.pmtiles', 'maxZoom': 6, 'build': 'https://example.org/build.pmtiles', 'version': '4.15.2'
    }))
    write_region(tmp_path, 'USA-ADM1-a', 'Mississippi (United States of America)')
    write_region(tmp_path, 'IRL', 'Ireland')
    write_region(tmp_path, 'LUX', 'Luxembourg', complete=False)  # its file is still being written
    assert write_tiles_json(tmp_path)

    tiles = json.loads((tmp_path / 'tiles.json').read_text())
    assert tiles['attribution'] == '© OpenStreetMap contributors, Protomaps'
    assert tiles['layers'] == [
        {'url': 'world.pmtiles', 'maxZoom': 6, 'build': 'https://example.org/build.pmtiles'},
        {'url': 'regions/IRL.pmtiles', 'name': 'Ireland', 'minZoom': 7, 'maxZoom': 15, 'bounds': [[0, 0], [1, 1]]},
        {'url': 'regions/USA-ADM1-a.pmtiles', 'name': 'Mississippi (United States of America)', 'minZoom': 7,
         'maxZoom': 15, 'bounds': [[0, 0], [1, 1]]},
    ]
    assert [sidecar['key'] for sidecar in read_sidecars(tmp_path)] == ['IRL', 'USA-ADM1-a']
    assert not list(tmp_path.glob('.*.partial'))
    assert tiles['countries'] == {}

    # and the extent to show each country by, divided ones included
    (tmp_path / 'countries').mkdir()
    for code, name in (('IRL', 'Ireland'), ('USA', 'United States of America')):
        (tmp_path / 'countries' / f'{code}.json').write_text(json.dumps({'name': name, 'bounds': [[0, 0], [1, 1]]}))
    assert write_tiles_json(tmp_path)
    assert json.loads((tmp_path / 'tiles.json').read_text())['countries'] == {
        'IRL': {'name': 'Ireland', 'bounds': [[0, 0], [1, 1]]},
        'USA': {'name': 'United States of America', 'bounds': [[0, 0], [1, 1]]}
    }
