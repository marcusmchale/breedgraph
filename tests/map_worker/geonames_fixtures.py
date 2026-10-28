"""
A few of GeoNames' places and files, as download.geonames.org/export/dump serves them, for the place search's tests:
Ireland's dump (Ballyduffs in three counties, Galway, Dublin, a farm, a mountain, places left out, a Northern Irish town
in Ireland's file), the world's towns (cities1000: Galway again, Qazvin, Windhoek), the countries' shapes (Ireland
with a far island, Fiji across 180°), and the admin and feature names.
"""
import json
import zipfile
from pathlib import Path

import httpx

GEONAMES_URL = 'https://geonames.test/export/dump'


def place(geonameid, name, latitude, longitude, feature_class, feature_code, country='IE', admin1='', admin2='',
          alternates='', population=0, asciiname=None) -> str:
    """A row of GeoNames' dumps: 19 fields, split by tabs"""
    return '\t'.join(str(field) for field in (
        geonameid, name, asciiname if asciiname is not None else name, alternates, latitude, longitude,
        feature_class, feature_code, country, '', admin1, admin2, '', '', population, '', '0', 'Europe/Dublin',
        '2026-10-28'
    ))


IRELAND = [
    place(2966605, 'Ballyduff', 52.45593, -9.66399, 'P', 'PPL', admin1='M', admin2='11', population=517,
          alternates='An Baile Dubh,Ballyduff,12345,ballyduff'),
    place(2966606, 'Ballyduff', 52.22972, -7.26083, 'P', 'PPL', admin1='M', admin2='44'),
    place(3313853, 'Ballyduff', 53.24611, -7.29278, 'P', 'PPL', admin1='L', admin2='23'),
    place(2964180, 'Galway', 53.27194, -9.04889, 'P', 'PPLA', admin1='C', admin2='10', population=79934,
          alternates='Gaillimh,Galway'),
    place(2964574, 'Dublin', 53.33306, -6.24889, 'P', 'PPLC', admin1='L', admin2='33', population=1024027,
          alternates='Baile Átha Cliath,BAC,Dublino'),
    place(2963517, 'Kerry', 52.16667, -9.75, 'A', 'ADM2', admin1='M', admin2='11', alternates='Ciarraí,County Kerry'),
    place(2962187, 'Uíbh Fhailí', 53.25, -7.5, 'A', 'ADM2', admin1='L', admin2='23', asciiname='Uibh Fhaili',
          alternates='County Offaly,Offaly'),
    place(7521315, 'Munster', 52.33333, -8.5, 'A', 'ADM1', admin1='M', alternates='Cúige Mumhan'),
    place(9000001, 'Oak Park', 52.86, -6.91, 'S', 'FRM', admin1='L', admin2='01'),
    place(9000002, 'Croagh Patrick', 53.75947, -9.65818, 'T', 'MT', admin1='C', admin2='20', alternates='Cruach Phádraig'),
    place(9000003, 'Old Road', 53.0, -8.0, 'R', 'RD'),
    place(9000004, 'Porcupine Bank', 53.5, -13.5, 'U', 'BNKU'),
    place(9000005, 'Old Ballyduff', 52.4, -9.6, 'P', 'PPLH', admin1='M', admin2='11'),
    place(9000006, 'Newry', 54.17, -6.34, 'P', 'PPL', country='GB'),
]
WORLD_TOWNS = [
    place(2964180, 'Galway', 53.27194, -9.04889, 'P', 'PPLA', admin1='C', admin2='10', population=79934,
          alternates='Gaillimh,Galway'),
    place(119208, 'Qazvin', 36.26877, 50.0041, 'P', 'PPLA', country='IR', admin1='28', population=402748,
          alternates='Kazvin,Qazvīn'),
    place(3352136, 'Windhoek', -22.55941, 17.08323, 'P', 'PPLC', country='NA', admin1='21', population=268132),
]
ADMIN1 = {'IE.M': 'Munster', 'IE.L': 'Leinster', 'IE.C': 'Connacht', 'IR.28': 'Qazvin', 'NA.21': 'Khomas'}
ADMIN2 = {'IE.M.11': 'Kerry', 'IE.M.44': 'County Waterford', 'IE.L.23': 'Uíbh Fhailí', 'IE.C.10': 'County Galway',
          'IE.L.01': 'County Carlow', 'IE.C.20': 'Mayo County', 'IE.L.33': 'Dublin City'}
FEATURES = {'P.PPL': 'populated place', 'P.PPLA': 'seat of a first-order administrative division',
            'P.PPLC': 'capital of a political entity', 'A.ADM1': 'first-order administrative division',
            'A.ADM2': 'second-order administrative division', 'S.FRM': 'farm', 'T.MT': 'mountain', 'R.RD': 'road'}


def square(west, south, east, north) -> list:
    return [[[west, south], [east, south], [east, north], [west, north], [west, south]]]


SHAPES = {
    # Ireland, and a far island of it a hundredth its size
    '2963597': {'type': 'MultiPolygon', 'coordinates': [square(-10.5, 51.4, -6.0, 55.4), square(-30.1, 51.0, -30.0, 51.1)]},
    # Fiji, across the antimeridian
    '2205218': {'type': 'MultiPolygon', 'coordinates': [square(177.0, -19.0, 180.0, -16.0), square(-180.0, -19.0, -178.5, -16.0)]},
    '0': {'type': 'Point', 'coordinates': [0, 0]},  # not an outline, left out
}


def _zip(path: Path, member: str, text: str) -> None:
    with zipfile.ZipFile(path, 'w') as zipped:
        zipped.writestr(member, text)


def write_site(directory: Path, ireland=IRELAND, towns=WORLD_TOWNS) -> Path:
    """GeoNames' files, as the site serves them, in directory"""
    directory.mkdir(parents=True, exist_ok=True)
    _zip(directory / 'IE.zip', 'IE.txt', '\n'.join(ireland) + '\n')
    _zip(directory / 'cities1000.zip', 'cities1000.txt', '\n'.join(towns) + '\n')
    _zip(directory / 'shapes_simplified_low.json.zip', 'shapes_simplified_low.json', json.dumps({
        'type': 'FeatureCollection',
        'features': [{'type': 'Feature', 'properties': {'geoNameId': key}, 'geometry': shape} for key, shape in SHAPES.items()]
    }))
    (directory / 'admin1CodesASCII.txt').write_text(''.join(f'{code}\t{name}\t{name}\t1\n' for code, name in ADMIN1.items()))
    (directory / 'admin2Codes.txt').write_text(''.join(f'{code}\t{name}\t{name}\t1\n' for code, name in ADMIN2.items()))
    (directory / 'featureCodes_en.txt').write_text(
        ''.join(f'{code}\t{label}\ta description\n' for code, label in FEATURES.items()) + 'null\t\t\n'
    )
    return directory


def serving(directory: Path, requests: list | None = None):
    """An httpx handler answering for GeoNames' site with the files in directory, 404 for any other"""
    def handle(request: httpx.Request) -> httpx.Response:
        if requests is not None:
            requests.append(request.url.path)
        path = directory / request.url.path.rsplit('/', 1)[-1]
        if not request.url.path.startswith(httpx.URL(GEONAMES_URL).path) or not path.is_file():
            return httpx.Response(404)
        return httpx.Response(200, content=path.read_bytes())
    return handle
