"""
GeoNames' places for the place search, as the map worker (or the API) downloads and writes them
(map_worker.fetching.download_gazetteer, write_gazetteer), from the few in geonames_fixtures.py: no request leaves
the test.
"""
import gzip
import json
import zipfile

import httpx
import pytest

from map_worker import fetching
from map_worker.fetching import (
    GAZETTEER_COLUMNS, MapRegionError, download_gazetteer, write_gazetteer, read_names, read_feature_labels, read_shapes
)
from tests.map_worker.geonames_fixtures import (
    GEONAMES_URL, IRELAND, WORLD_TOWNS, ADMIN1, ADMIN2, FEATURES, place, write_site, serving
)

REAL_CLIENT = httpx.AsyncClient


def rows(path) -> list[dict]:
    with gzip.open(path, 'rt', encoding='utf-8') as f:
        header = f.readline().rstrip('\n').split('\t')
        assert tuple(header) == GAZETTEER_COLUMNS
        return [dict(zip(header, line.rstrip('\n').split('\t'))) for line in f]


def dump(tmp_path, places, member='IE.txt'):
    archive = tmp_path / 'dump.zip'
    with zipfile.ZipFile(archive, 'w') as zipped:
        zipped.writestr(member, '\n'.join(places) + '\n')
    return archive


def test_a_countrys_places_are_written_with_their_sections_and_kind(tmp_path):
    output = tmp_path / 'IRL.tsv.gz'
    assert write_gazetteer(dump(tmp_path, IRELAND), 'IE.txt', output, 'IE', ADMIN1, ADMIN2, FEATURES) == 10
    found = rows(output)
    written = {row['geonameid']: row for row in found if row['geonameid']}
    # roads, undersea features and places no longer there are left out, and so is a place of another country
    assert set(written) == {'2966605', '2966606', '3313853', '2964180', '2964574', '2963517', '2962187', '7521315',
                            '9000001', '9000002'}
    kerry = written['2966605']
    assert (kerry['name'], kerry['feature'], kerry['country'], kerry['admin1'], kerry['admin2'], kerry['population']) \
        == ('Ballyduff', 'populated place', 'IE', 'Munster', 'Kerry', '517')
    assert kerry['alternatenames'] == 'An Baile Dubh', 'no postcodes, nor its own name again'
    assert written['3313853']['admin2'] == 'Uíbh Fhailí'
    # the other names of its sections, given once each, before the places: a county's then its province's
    regions = [(row['country'], row['admin1'], row['admin2'], row['region_alternates']) for row in found[:4]]
    assert sorted(regions) == [
        ('IE', 'Leinster', 'Uíbh Fhailí', 'County Offaly,Offaly'),
        ('IE', 'Munster', '', 'Cúige Mumhan'),
        ('IE', 'Munster', 'County Waterford', 'Cúige Mumhan'),
        ('IE', 'Munster', 'Kerry', 'Ciarraí,County Kerry,Cúige Mumhan'),
    ]
    assert all(row['geonameid'] for row in found[4:]) and not any(row['region_alternates'] for row in found[4:])
    assert written['9000001']['feature'] == 'farm'
    assert all(row['shape'] == '' for row in written.values())


def test_the_worlds_towns_end_with_the_countries_shapes(tmp_path):
    site = write_site(tmp_path / 'site')
    shapes = read_shapes(site / 'shapes_simplified_low.json.zip')
    assert set(shapes) == {'2963597', '2205218'}, 'only outlines'
    output = tmp_path / 'world.tsv.gz'
    assert write_gazetteer(site / 'cities1000.zip', 'cities1000.txt', output, None, ADMIN1, ADMIN2, FEATURES, shapes) == 3
    written = rows(output)
    towns, outlines = written[:3], written[3:]
    assert [(t['name'], t['country'], t['admin1']) for t in towns] \
        == [('Galway', 'IE', 'Connacht'), ('Qazvin', 'IR', 'Qazvin'), ('Windhoek', 'NA', 'Khomas')]
    assert {(o['geonameid'], o['feature_class'], o['feature_code']) for o in outlines} \
        == {('2963597', 'A', 'PCLI'), ('2205218', 'A', 'PCLI')}
    assert json.loads(next(o for o in outlines if o['geonameid'] == '2205218')['shape'])['type'] == 'MultiPolygon'


def test_a_few_malformed_rows_are_left_out_but_more_refuse_the_file(tmp_path):
    towns = [place(100 + i, f'Town {i}', 53.0, -8.0, 'P', 'PPL') for i in range(200)]
    output = tmp_path / 'out.tsv.gz'
    assert write_gazetteer(dump(tmp_path, towns + ['broken\trow']), 'IE.txt', output, 'IE', {}, {}, {}) == 200
    bad = towns[:20] + ['broken\trow', place('x', 'No id', 53.0, -8.0, 'P', 'PPL'), place(1, 'Off the map', 95, 0, 'P', 'PPL')]
    with pytest.raises(MapRegionError, match='3 of .* rows .* are malformed'):
        write_gazetteer(dump(tmp_path, bad), 'IE.txt', output, 'IE', {}, {}, {})
    with pytest.raises(MapRegionError, match='has no places'):
        write_gazetteer(dump(tmp_path, [place(1, 'Road', 53, -8, 'R', 'RD')]), 'IE.txt', output, 'IE', {}, {}, {})


def test_names_and_labels_are_read_from_geonames_files():
    assert read_names('IE.M\tMunster\tMunster\t7521315\nNA.21\tKhomas\tKhomas\t3371199\nbad\n') \
        == {'IE.M': 'Munster', 'NA.21': 'Khomas'}
    assert read_feature_labels('S.FRM\tfarm\ta tract of land\nnull\t\t\n') == {'S.FRM': 'farm'}


@pytest.fixture
def geonames(tmp_path, monkeypatch):
    """GeoNames' site, answered from geonames_fixtures.py, and the requests made of it"""
    site, requests = write_site(tmp_path / 'site'), []
    monkeypatch.setattr(fetching.httpx, 'AsyncClient',
                        lambda **kwargs: REAL_CLIENT(transport=httpx.MockTransport(serving(site, requests)), **kwargs))
    return site, requests


@pytest.mark.asyncio
async def test_a_countrys_places_are_downloaded_and_its_archive_deleted(geonames, tmp_path):
    output = tmp_path / 'work' / 'IRL.tsv.gz'
    output.parent.mkdir()
    assert await download_gazetteer(GEONAMES_URL, 'IRL', 'IE', output) == 10
    assert sorted(p.name for p in output.parent.iterdir()) == ['IRL.tsv.gz']
    assert geonames[1][-1].endswith('/IE.zip')


@pytest.mark.asyncio
async def test_the_worlds_places_are_downloaded(geonames, tmp_path):
    output = tmp_path / 'world.tsv.gz'
    assert await download_gazetteer(GEONAMES_URL, 'world', None, output) == len(WORLD_TOWNS)
    assert {path.rsplit('/', 1)[-1] for path in geonames[1]} >= {'cities1000.zip', 'shapes_simplified_low.json.zip'}


@pytest.mark.asyncio
async def test_what_cannot_be_downloaded_or_read_fails_the_job(geonames, tmp_path, monkeypatch):
    output = tmp_path / 'out.tsv.gz'
    with pytest.raises(MapRegionError, match='GeoNames has no FR.zip'):
        await download_gazetteer(GEONAMES_URL, 'FRA', 'FR', output)
    (geonames[0] / 'IE.zip').write_bytes(b'not a zip')
    with pytest.raises(MapRegionError, match='could not be read: BadZipFile'):
        await download_gazetteer(GEONAMES_URL, 'IRL', 'IE', output)
    with zipfile.ZipFile(geonames[0] / 'IE.zip', 'w') as zipped:
        zipped.writestr('readme.txt', 'no places')
    with pytest.raises(MapRegionError, match='could not be read: KeyError'):
        await download_gazetteer(GEONAMES_URL, 'IRL', 'IE', output)
    monkeypatch.setattr(fetching, 'ARCHIVE_MAX_BYTES', 10)
    with pytest.raises(MapRegionError, match='larger than 10 bytes'):
        await download_gazetteer(GEONAMES_URL, 'IRL', 'IE', output)
    assert not [p for p in tmp_path.iterdir() if p.name.startswith('.')], 'no archive is left behind'
