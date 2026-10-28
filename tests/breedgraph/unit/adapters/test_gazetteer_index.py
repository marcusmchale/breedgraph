"""
The place search's database (adapters/geonames/index.py), loaded from files the map worker writes
(map_worker.fetching.write_gazetteer) of the few places in tests/map_worker/geonames_fixtures.py. Runs with
--noconftest.
"""
import gzip
import sqlite3
import zipfile

import pytest

from breedgraph.adapters.geonames import index as gazetteer
from breedgraph.adapters.geonames.countries import read_countries
from breedgraph.adapters.geonames.index import (
    GazetteerIndex, GazetteerFileError, SearchTooLong, normalize, words, label_for, zoom_for, region_for
)
from map_worker.fetching import GAZETTEER_COLUMNS, write_gazetteer, read_shapes
from tests.map_worker.geonames_fixtures import IRELAND, WORLD_TOWNS, ADMIN1, ADMIN2, FEATURES, place, write_site

EXTRA_IRISH = [
    place(2963597, 'Éire', 53.0, -8.0, 'A', 'PCLI', population=4977400, alternates='Ireland,Irlanda'),
    place(9000020, 'Kings', 53.1, -7.1, 'P', 'PPL'),
    place(9000021, 'Kingscourt', 53.9, -6.8, 'P', 'PPL', population=1300),
    place(9000022, 'Montevallo', 53.2, -7.2, 'P', 'PPL', population=5000, alternates='Kings'),
]
EXTRA_TOWNS = [
    place(2204668, 'Levuka', -17.68, 178.83, 'P', 'PPL', country='FJ', population=1131),
    place(9000030, 'Levuka', 40.0, -100.0, 'P', 'PPL', country='US', population=90000),
]
IRISH_COUNTIES = {'Kerry, Munster', 'County Waterford, Munster', 'Uíbh Fhailí, Leinster'}


def zipped(path, member, rows):
    with zipfile.ZipFile(path, 'w') as archive:
        archive.writestr(member, '\n'.join(rows) + '\n')
    return path


@pytest.fixture
def files(tmp_path):
    """The world's file and Ireland's, as the map worker sends them"""
    site = write_site(tmp_path / 'site', towns=WORLD_TOWNS + EXTRA_TOWNS)
    world, ireland = tmp_path / 'world.tsv.gz', tmp_path / 'IRL.tsv.gz'
    write_gazetteer(site / 'cities1000.zip', 'cities1000.txt', world, None, ADMIN1, ADMIN2, FEATURES,
                    read_shapes(site / 'shapes_simplified_low.json.zip'))
    write_gazetteer(zipped(tmp_path / 'IE.zip', 'IE.txt', IRELAND + EXTRA_IRISH), 'IE.txt', ireland, 'IE', ADMIN1,
                    ADMIN2, FEATURES)
    return world, ireland


@pytest.fixture
def index(tmp_path):
    made = GazetteerIndex(tmp_path / 'gazetteer' / 'gazetteer.sqlite')
    made.create(read_countries().values())
    return made


@pytest.fixture
def loaded(index, files):
    world, ireland = files
    index.load_world(world)
    index.load_country('IRL', ireland)
    return index


def names(places) -> list:
    return [p.name for p in places]


def test_names_are_searched_without_case_accents_or_apostrophes():
    assert normalize('Baile Átha Cliath') == 'baile atha cliath'
    assert normalize('  Dublin,  Ireland ') == 'dublin ireland'
    assert (normalize("King's Lynn"), normalize("King’s Lynn", '')) == ('king s lynn', 'kings lynn')
    assert (normalize('Łódź'), normalize('Straße'), normalize('Øresund')) == ('lodz', 'strasse', 'oresund')
    assert normalize('Qazvīn') == 'qazvin'
    assert words('"Ballyduff" AND * ^Kerry: NEAR(') == ['ballyduff', 'and', 'kerry', 'near']
    assert words('" * ^ : ( )') == []


@pytest.mark.parametrize('query', [
    'NEAR(', '"', '*', 'ballyduff OR kerry', "'; DROP TABLE places; --", '{names}: x', '^galway', 'galway"*', 'a' * 5000,
    'NOT', '-ballyduff', 'ballyduff + kerry'
])
def test_no_query_is_read_as_fts5s_syntax(loaded, query):
    loaded.search(query)
    assert names(loaded.search('^galway"*'))[0] == 'Galway'


def test_a_countrys_places_are_found_with_their_kind_and_region(loaded):
    found = loaded.search('Ballyduff')
    assert names(found) == ['Ballyduff'] * 3, 'not the one no longer there, which the worker leaves out'
    assert {p.region for p in found} == IRISH_COUNTIES
    kerry = found[0]
    assert (kerry.region, kerry.description, kerry.country, kerry.zoom, kerry.bounds) \
        == ('Kerry, Munster', 'village', 'Ireland', 14, None), 'the largest first'
    assert {p.description for p in found[1:]} == {'town or village'}, 'no population given'

    farm = loaded.search('oak park')[0]
    assert (farm.name, farm.description, farm.zoom, farm.region) == ('Oak Park', 'farm', 16, 'County Carlow, Leinster')
    county = loaded.search('kerry')[0]
    assert (county.name, county.description, county.region, county.zoom) \
        == ('Kerry', 'county or district', 'Munster', 9), 'its own name not given again as its region'


def test_other_names_find_a_place(loaded):
    assert names(loaded.search('Gaillimh')) == ['Galway']
    assert names(loaded.search('baile atha cliath')) == ['Dublin']
    assert names(loaded.search('Cruach Phádraig')) == ['Croagh Patrick']
    assert loaded.search('cruach')[0].description == 'mountain'


def test_other_words_may_name_the_region(loaded):
    assert [p.region for p in loaded.search('ballyduff kerry')] == ['Kerry, Munster']
    assert [p.region for p in loaded.search('ballyduff ker')] == ['Kerry, Munster'], 'the last word as it is typed'
    assert [p.region for p in loaded.search('ballyduff offaly')] == ['Uíbh Fhailí, Leinster'], "the county's other names"
    assert [p.region for p in loaded.search('ballyduff ireland')] == [
        'Kerry, Munster', 'County Waterford, Munster', 'Uíbh Fhailí, Leinster'
    ], 'or the country'
    assert [p.region for p in loaded.search('kerry ballyduff')] == ['Kerry, Munster'], 'the place named second'
    assert loaded.search('ballyduff connacht') == []


def test_whole_names_come_first_then_names_started_then_other_names(loaded):
    assert names(loaded.search('kings', limit=3)) == ['Kings', 'Kingscourt', 'Montevallo']
    assert names(loaded.search('dub'))[0] == 'Dublin'
    assert loaded.search('d') == [], 'a single letter is a whole name, not the start of every name'
    assert [p.region for p in loaded.search('ballyduff k')] == ['Kerry, Munster'], "but a region's may start with it"


def test_the_worlds_towns_are_found_until_a_countrys_own_places_are_loaded(index, files):
    world, ireland = files
    index.load_world(world)
    galway = index.search('galway')
    assert [(p.name, p.region, p.country) for p in galway] == [('Galway', 'County Galway, Connacht', 'Ireland')]
    assert index.search('ballyduff') == [] and index.loaded() == set()
    assert [(p.name, p.country, p.description) for p in index.search('qazvin')] == [('Qazvin', 'Iran', 'city')]

    index.load_country('IRL', ireland)
    assert names(index.search('galway')) == ['Galway'], "Ireland's own Galway, not the world's too"
    assert index.loaded() == {'IRL'}

    index.remove_country('IRL')
    assert index.search('ballyduff') == [] and index.loaded() == set()
    assert names(index.search('galway')) == ['Galway'], "the world's again"
    assert names(index.search('qazvin')) == ['Qazvin']


def test_countries_are_places_shown_by_their_main_parts(index, files):
    index.load_world(files[0])
    ireland = index.search('ireland')[0]
    assert (ireland.name, ireland.description, ireland.zoom, ireland.country) == ('Ireland', 'country', None, None)
    assert ireland.bounds == [[51.4, -10.5], [55.4, -6.0]], 'its far island left out'
    fiji = index.country_place('FJI')
    assert fiji.bounds == [[-19.0, 177.0], [-16.0, 181.5]], 'across the antimeridian, east above 180'
    assert fiji.longitude == pytest.approx(179.25)
    assert index.country_place('FRA') is None, 'GeoNames gave no shape'
    assert index.country_place('XYZ') is None

    index.load_country('IRL', files[1])
    ireland = index.search('ireland')[0]
    assert (ireland.name, ireland.bounds) == ('Ireland', [[51.4, -10.5], [55.4, -6.0]]), \
        'its own row, named as BreedGraph names it, rather than Éire'
    assert names(index.search('éire')) == ['Ireland']


def test_a_viewbox_comes_before_importance_or_bounds_the_search(index, files):
    index.load_world(files[0])
    assert [p.country for p in index.search('levuka')] == ['United States', 'Fiji'], 'the larger first'
    across = [170, -25, 190, -10]  # as Leaflet gives a view across the antimeridian
    assert [p.country for p in index.search('levuka', viewbox=across)] == ['Fiji', 'United States']
    assert [p.country for p in index.search('levuka', viewbox=[-185, -25, -170, -10], bounded=True)] == ['Fiji']
    assert [p.country for p in index.search('levuka', viewbox=[-110, 30, -90, 50], bounded=True)] == ['United States']
    assert len(index.search('levuka', viewbox=[-200, -90, 200, 90], bounded=True)) == 2, 'the whole world'


def test_a_country_bounds_the_search(loaded):
    assert loaded.search('galway', country='IRN') == []
    assert names(loaded.search('qazvin', country='IRN')) == ['Qazvin']


@pytest.mark.parametrize('viewbox', [[1, 2, 3], [0, 10, 1, 5], [0, -95, 1, 5], ['a', 0, 1, 1], [float('nan'), 0, 1, 1]])
def test_a_bad_viewbox_is_refused(loaded, viewbox):
    with pytest.raises(ValueError, match='west, south, east, north'):
        loaded.search('galway', viewbox=viewbox)


def test_a_search_longer_than_its_time_is_stopped(loaded, monkeypatch):
    monkeypatch.setattr(gazetteer, 'SEARCH_SECONDS', -1)
    monkeypatch.setattr(gazetteer, 'PROGRESS_STEPS', 1)
    with pytest.raises(SearchTooLong):
        loaded.search('b')


def test_searches_go_on_while_a_country_is_written(loaded):
    with loaded._writing() as db:
        loaded._delete(db, "country = 'IRL' AND source = 'country'")
        assert len(loaded.search('ballyduff')) == 3, 'what was there before the load'
    assert loaded.search('ballyduff') == []


def check_the_indexes(index):
    """Both text indexes hold what their tables do, and no region is left without places"""
    with sqlite3.connect(index.path) as db:
        db.execute("INSERT INTO places_text (places_text) VALUES ('integrity-check')")
        db.execute("INSERT INTO regions_text (regions_text) VALUES ('integrity-check')")
        assert db.execute('SELECT count(*) FROM regions WHERE id NOT IN (SELECT region FROM places)').fetchone() == (0,)
        return db.execute('SELECT count(*) FROM regions').fetchone()[0], db.execute('SELECT count(*) FROM places').fetchone()[0]


def test_regions_are_kept_once_and_removed_with_their_places(index, files):
    world, ireland = files
    index.load_world(world)
    regions, places = check_the_indexes(index)
    index.load_country('IRL', ireland)
    index.load_country('IRL', ireland)
    assert check_the_indexes(index)[0] < check_the_indexes(index)[1]
    index.remove_country('IRL')
    assert check_the_indexes(index) == (regions, places)
    index.load_world(world)
    assert check_the_indexes(index) == (regions, places)


def write_places(path, rows, header=GAZETTEER_COLUMNS):
    with gzip.open(path, 'wt', encoding='utf-8') as f:
        f.write('\t'.join(header) + '\n' + ''.join('\t'.join(row) + '\n' for row in rows))
    return path


def row(geonameid='1', name='Town', latitude='53', longitude='-8', country='IE') -> list:
    fields = dict.fromkeys(GAZETTEER_COLUMNS, '') | {
        'geonameid': geonameid, 'name': name, 'latitude': latitude, 'longitude': longitude, 'feature_class': 'P',
        'feature_code': 'PPL', 'country': country, 'population': '0'
    }
    return list(fields.values())


def test_a_bad_file_is_refused_and_the_places_kept(loaded, tmp_path):
    bad = tmp_path / 'bad.tsv.gz'
    bad.write_bytes(b'\x1f\x8bnot really gzip')
    with pytest.raises(GazetteerFileError, match='could not be read'):
        loaded.load_country('IRL', bad)
    with pytest.raises(GazetteerFileError, match='not a file of places'):
        loaded.load_country('IRL', write_places(bad, [row()], header=('geonameid', 'name')))
    towns = [row(str(i)) for i in range(1, 200)]
    with pytest.raises(GazetteerFileError, match='3 of 202 places in bad.tsv.gz are malformed'):
        loaded.load_country('IRL', write_places(bad, towns + [row('x'), row(latitude='95'), ['short']]))
    with pytest.raises(GazetteerFileError, match='XYZ is not one of the countries'):
        loaded.load_country('XYZ', write_places(bad, towns))
    assert len(loaded.search('ballyduff')) == 3 and loaded.loaded() == {'IRL'}
    check_the_indexes(loaded)

    assert loaded.load_country('IRL', write_places(bad, towns + [row('x'), row(country='GB')])) == 199, \
        'a few malformed, and places of other countries left out'


def test_the_database_is_made_again_by_another_version(index, files):
    index.load_world(files[0])
    assert index.create(read_countries().values()) is False
    assert names(index.search('galway')) == ['Galway']
    with sqlite3.connect(index.path) as db:
        db.execute('PRAGMA user_version = 99')
    assert index.create(read_countries().values()) is True
    assert index.search('galway') == [] and index.country_place('IRL') is None
    index.path.write_bytes(b'not a database at all')
    assert index.create(read_countries().values()) is True
    assert index.search('galway') == []


def test_kinds_zooms_and_regions_in_words():
    assert [label_for('P', 'PPL', 'populated place', n) for n in (0, 517, 5000, 200_000)] \
        == ['town or village', 'village', 'town', 'city']
    assert (label_for('P', 'PPLC', '', 1), label_for('S', 'FRM', 'farm', 0), label_for('A', 'PCLI', '', 0)) \
        == ('capital', 'farm', 'country')
    assert (zoom_for('S', 'FRM', 0), zoom_for('P', 'PPL', 0), zoom_for('P', 'PPL', 5000), zoom_for('A', 'ADM2', 0)) \
        == (16, 14, 12, 9)
    assert region_for('Ballyduff', 'Kerry', 'Munster') == 'Kerry, Munster'
    assert region_for('Kerry', 'Kerry', 'Munster') == 'Munster'
    assert region_for('Bogotá', 'Bogotá  D.C.', 'Bogota D.C.') == 'Bogotá  D.C.'
    assert region_for('Munster', '', 'Munster') is None


def test_the_room_places_took_is_given_back_when_they_go(index, files, tmp_path):
    index.load_world(files[0])
    before = index.path.stat().st_size
    towns = [row(str(i), f'Town {i} of a large county') for i in range(1, 3000)]
    index.load_country('IRL', write_places(tmp_path / 'IRL.tsv.gz', towns))
    assert index.path.stat().st_size > before * 2
    index.remove_country('IRL')
    with sqlite3.connect(index.path) as db:
        assert db.execute('PRAGMA freelist_count').fetchone() == (0,)
    assert index.path.stat().st_size < before * 1.5
