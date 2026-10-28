"""
What fetching maps needs from the internet (breedgraph docs/maps.md): Protomaps' list of builds, the go-pmtiles
command that cuts regions out of a build reading only the parts it needs, geoBoundaries' outlines of countries and
their sections, and GeoNames' places for the place search.

The map worker runs these for the API on a server with internet access; the API runs them itself when it fetches its
own maps (breedgraph adapters/pmtiles). So this module needs only the standard library and httpx, and reads no
environment: both pass in their settings.
"""
import asyncio
import gzip
import io
import json
import math
import re
import shutil
import zipfile
from pathlib import Path
from typing import Dict, List, Tuple

import httpx

import logging
logger = logging.getLogger(__name__)

# Each of Protomaps' daily builds is served here, followed by its key
PROTOMAPS_BUILD_URL = 'https://build.protomaps.com/'
HEADERS = {'User-Agent': 'BreedGraph'}
# what geoBoundaries says about a country's outlines that is kept beside them: its source and licence
ABOUT = ('boundaryID', 'boundaryName', 'boundaryLicense', 'licenseSource', 'buildDate')

_ARCHIVE_SIZE = re.compile(r'archive size of ([\d.]+) ?([kKMGTPE]?)B\b')
_UNITS = {'': 1, 'k': 1e3, 'K': 1e3, 'M': 1e6, 'G': 1e9, 'T': 1e12, 'P': 1e15, 'E': 1e18}


class MapRegionError(Exception):
    """A region that could not be fetched. The message is for the log only."""


def parse_archive_size(output: str) -> int:
    """The size in bytes reported by pmtiles extract --dry-run, e.g. '... for an archive size of 454 MB'"""
    matches = _ARCHIVE_SIZE.findall(output)
    if not matches:
        raise MapRegionError(f"pmtiles reported no archive size: {output[-500:]}")
    number, unit = matches[-1]
    return int(float(number) * _UNITS[unit])


class PmtilesCommand:

    def __init__(self, command: str):
        self.command = command

    def available(self) -> bool:
        return bool(self.command) and shutil.which(self.command) is not None

    async def _run(self, *arguments: str) -> str:
        """Its output; the command is stopped if the task is cancelled"""
        process = await asyncio.create_subprocess_exec(
            self.command, *arguments, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.STDOUT
        )
        try:
            output, _ = await process.communicate()
        except asyncio.CancelledError:
            if process.returncode is None:
                process.terminate()
                try:
                    await asyncio.wait_for(process.wait(), 10)
                except TimeoutError:
                    process.kill()
            raise
        output = output.decode(errors='replace')
        if process.returncode != 0:
            raise MapRegionError(f"pmtiles {arguments[0]} exited with {process.returncode}: {output[-500:]}")
        return output

    @staticmethod
    def _options(outline: Path | None, minzoom: int, maxzoom: int) -> List[str]:
        """The region's outline, or the whole world without one, between the zooms"""
        region = [f'--region={outline}'] if outline is not None else []
        return [*region, f'--minzoom={minzoom}', f'--maxzoom={maxzoom}']

    async def size(self, build: str, outline: Path | None, minzoom: int, maxzoom: int, key: str | None = None) -> int:
        """
        The size in bytes of the region's file, from a dry run that reads only the build's directories.
        key names the region (or 'world'); the command doesn't need it, the map worker's jobs do.
        """
        output = await self._run('extract', build, '/dev/null', *self._options(outline, minzoom, maxzoom), '--dry-run')
        return parse_archive_size(output)

    async def extract(
            self,
            build: str,
            outline: Path | None,
            output: Path,
            minzoom: int,
            maxzoom: int,
            key: str | None = None,
            version: str | None = None,
            fresh: bool = False
    ) -> Tuple[str, str | None] | None:
        """
        Cut the region into output. As for size, key, version (of the build's tiles) and fresh (not a file the map
        worker kept) are for the map worker's jobs, which return the build and version the file was cut from; the
        command returns None, having cut it from build.
        """
        await self._run('extract', build, str(output), *self._options(outline, minzoom, maxzoom), '--quiet')
        return None


def latest_build(builds: List[dict], major: str | None = None) -> dict | None:
    """The newest build, of the given major version of the tiles, to match the world file and the map's style"""
    builds = [build for build in builds if str(build.get('key', '')).endswith('.pmtiles')]
    if major is not None:
        builds = [build for build in builds if str(build.get('version', '')).split('.')[0] == major]
    return max(builds, key=lambda build: build['key'], default=None)


async def list_builds(url: str) -> List[dict]:
    """Protomaps' list of builds, each {key, version, ...}"""
    try:
        async with httpx.AsyncClient(timeout=30, headers=HEADERS) as client:
            response = await client.get(url)
            response.raise_for_status()
            builds = response.json()
    except (httpx.HTTPError, ValueError) as e:
        raise MapRegionError(f"The list of Protomaps builds could not be read: {type(e).__name__}")
    if not isinstance(builds, list):
        raise MapRegionError("The list of Protomaps builds is not a list")
    return builds


async def download_outlines(url: str, code: str, level: str) -> Tuple[dict, dict]:
    """
    geoBoundaries' outlines of the country with this ISO 3166 alpha-3 code (ADM0) or its sections at that level (ADM1,
    ADM2), simplified: what it says about them (ABOUT: their source and licence, which vary by country) and the
    outlines themselves, a GeoJSON FeatureCollection
    """
    try:
        async with httpx.AsyncClient(timeout=120, follow_redirects=True, headers=HEADERS) as client:
            response = await client.get(f"{url}/{code}/{level}/")
            if response.status_code == 404:
                raise MapRegionError(f"geoBoundaries has no {level} outlines for {code}")
            response.raise_for_status()
            about = response.json()
            response = await client.get(about['simplifiedGeometryGeoJSON'])
            response.raise_for_status()
            outlines = response.json()
    except (httpx.HTTPError, ValueError, KeyError, TypeError) as e:
        raise MapRegionError(f"The {level} outlines for {code} could not be downloaded: {type(e).__name__}")
    if not isinstance(outlines, dict) or not outlines.get('features'):
        raise MapRegionError(f"geoBoundaries returned no {level} outlines for {code}")
    return {key: about.get(key) for key in ABOUT}, outlines


""" GeoNames' places, for the place search (breedgraph docs/maps.md, Place search) """

# What is sent for a country or the world: a gzipped TSV with these columns, on a first line of their own. The
# country is GeoNames' alpha-2 code; admin1 and admin2 name the sections a place is in, and region_alternates their
# other names, from their own rows (County Offaly for Uíbh Fhailí), so that a search may name them either way. The
# world's file ends with the countries' outlines, one row each, with only their geonameid, class A, code PCLI and the
# shape, as compact GeoJSON.
GAZETTEER_COLUMNS = (
    'geonameid', 'name', 'asciiname', 'alternatenames', 'latitude', 'longitude', 'feature_class', 'feature_code',
    'feature', 'country', 'admin1', 'admin2', 'region_alternates', 'population', 'modified', 'shape'
)
GAZETTEER_WORLD = 'world'
# Left out, as no field trial is placed by them: roads, railways and trails, undersea features, and places no longer
# there (historical, abandoned or destroyed)
LEFT_OUT_CLASSES = frozenset({'R', 'U'})
LEFT_OUT_CODES = frozenset({'ADM1H', 'ADM2H', 'ADM3H', 'ADM4H', 'ADM5H', 'ADMDH', 'PCLH', 'PPLH', 'PPLQ', 'PPLW'})
ALTERNATES_MAX = 4000  # characters of a place's alternate names kept
REGION_ALTERNATES_MAX = 1000  # and of its sections'
MALFORMED_SHARE = 0.01  # of a file's rows, above which it is refused
ARCHIVE_MAX_BYTES = 300 * 10 ** 6  # a download (the United States' is 71 MB)
MEMBER_MAX_BYTES = 2 * 10 ** 9  # unzipped
_LETTER = re.compile(r'[^\W\d_]')


def read_names(text: str) -> Dict[str, str]:
    """GeoNames' admin1CodesASCII.txt or admin2Codes.txt: names by code, e.g. IE.M: Munster, IE.M.11: Kerry"""
    names = {}
    for line in text.splitlines():
        fields = line.split('\t')
        if len(fields) >= 2 and fields[0] and fields[1]:
            names[fields[0]] = fields[1]
    return names


def read_feature_labels(text: str) -> Dict[str, str]:
    """GeoNames' featureCodes_en.txt: what each class and code is, e.g. S.FRM: farm"""
    labels = {}
    for line in text.splitlines():
        fields = line.split('\t')
        if len(fields) >= 2 and '.' in fields[0] and fields[1]:
            labels[fields[0]] = fields[1]
    return labels


def read_shapes(archive: Path) -> Dict[str, dict]:
    """The countries' simplified outlines (shapes_simplified_low.json.zip), by geonameid"""
    with zipfile.ZipFile(archive) as zipped:
        info = zipped.getinfo('shapes_simplified_low.json')
        if info.file_size > MEMBER_MAX_BYTES:
            raise MapRegionError("GeoNames' country shapes are too large")
        collection = json.loads(zipped.read(info).decode('utf-8'))
    shapes = {}
    for feature in collection.get('features') or []:
        geonameid = str((feature.get('properties') or {}).get('geoNameId') or '')
        geometry = feature.get('geometry') or {}
        if geonameid.isdigit() and geometry.get('type') in ('Polygon', 'MultiPolygon'):
            shapes[geonameid] = geometry
    if not shapes:
        raise MapRegionError("GeoNames' country shapes hold none")
    return shapes


def _alternates(names: str, name: str, asciiname: str, most: int = ALTERNATES_MAX) -> str:
    """A place's other names: those with letters (not postcodes), each once, apart from its name"""
    seen = {name.casefold(), asciiname.casefold()}
    kept, length = [], 0
    for alternate in names.split(','):
        alternate = alternate.strip()
        if not alternate or not _LETTER.search(alternate) or alternate.casefold() in seen:
            continue
        if length + len(alternate) + 1 > most:
            break
        seen.add(alternate.casefold())
        kept.append(alternate)
        length += len(alternate) + 1
    return ','.join(kept)


def write_gazetteer(
        archive: Path,
        member: str,
        output: Path,
        country: str | None,
        admin1: Dict[str, str],
        admin2: Dict[str, str],
        features: Dict[str, str],
        shapes: Dict[str, dict] | None = None
) -> int:
    """
    Write the places of GeoNames' file (member of the zip archive) to output, as GAZETTEER_COLUMNS: only the country's
    (alpha-2), when given, and none of the classes and codes left out, with their admin sections and kind named, and
    then the shapes, when given. Returns the places written. Refuses a file with no places, or more than
    MALFORMED_SHARE of its rows malformed.
    """
    rows = malformed = written = 0
    with zipfile.ZipFile(archive) as zipped:
        info = zipped.getinfo(member)
        if info.file_size > MEMBER_MAX_BYTES:
            raise MapRegionError(f"GeoNames' {member} is larger than {MEMBER_MAX_BYTES} bytes unzipped")
        sections = _section_alternates(zipped, info)
        with zipped.open(info) as raw, gzip.open(output, 'wt', encoding='utf-8', newline='\n') as out:
            out.write('\t'.join(GAZETTEER_COLUMNS) + '\n')
            for line in io.TextIOWrapper(raw, encoding='utf-8', newline='\n'):
                fields = line.rstrip('\r\n').split('\t')
                if fields == ['']:
                    continue
                rows += 1
                if len(fields) != 19:
                    malformed += 1
                    continue
                (geonameid, name, asciiname, alternates, latitude, longitude, feature_class, feature_code, code,
                 _, a1, a2, _, _, population, _, _, _, modified) = fields
                try:
                    latitude_, longitude_ = float(latitude), float(longitude)
                except ValueError:
                    malformed += 1
                    continue
                if not geonameid.isdigit() or not name or not -90 <= latitude_ <= 90 or not -180 <= longitude_ <= 180 \
                        or not math.isfinite(latitude_ + longitude_):
                    malformed += 1
                    continue
                if (country and code != country) or feature_class in LEFT_OUT_CLASSES or feature_code in LEFT_OUT_CODES:
                    continue
                section1 = f'{code}.{a1}' if a1 else None
                section2 = f'{code}.{a1}.{a2}' if a1 and a2 else None
                region_alternates = ','.join(sections[section] for section in (section2, section1) if section in sections)
                out.write('\t'.join((
                    geonameid, name, asciiname, _alternates(alternates, name, asciiname), latitude, longitude,
                    feature_class, feature_code, features.get(f'{feature_class}.{feature_code}', ''), code,
                    admin1.get(section1, '') if section1 else '', admin2.get(section2, '') if section2 else '',
                    region_alternates[:REGION_ALTERNATES_MAX], population if population.isdigit() else '0', modified, ''
                )) + '\n')
                written += 1
            for geonameid, shape in (shapes or {}).items():
                shape_ = json.dumps(shape, separators=(',', ':'))
                out.write('\t'.join((geonameid, '', '', '', '', '', 'A', 'PCLI', '', '', '', '', '', '0', '', shape_)) + '\n')
    if rows and malformed > rows * MALFORMED_SHARE:
        raise MapRegionError(f"{malformed} of GeoNames' {rows} rows in {member} are malformed")
    if not written:
        raise MapRegionError(f"GeoNames' {member} has no places")
    return written


def _section_alternates(zipped: zipfile.ZipFile, info: zipfile.ZipInfo) -> Dict[str, str]:
    """
    The other names of the file's first- and second-level sections (ADM1, ADM2), by their codes as admin1CodesASCII.txt
    and admin2Codes.txt give them (IE.L.23), from their own rows: a first pass over the file
    """
    sections = {}
    with zipped.open(info) as raw:
        for line in io.TextIOWrapper(raw, encoding='utf-8', newline='\n'):
            fields = line.rstrip('\r\n').split('\t')
            if len(fields) != 19 or fields[6] != 'A' or fields[7] not in ('ADM1', 'ADM2'):
                continue
            code, a1, a2 = fields[8], fields[10], fields[11]
            section = f'{code}.{a1}' if fields[7] == 'ADM1' else f'{code}.{a1}.{a2}'
            sections[section] = _alternates(fields[3], fields[1], fields[2], REGION_ALTERNATES_MAX // 2)
    return sections


async def _download(client: httpx.AsyncClient, url: str, path: Path) -> None:
    max_bytes = ARCHIVE_MAX_BYTES
    async with client.stream('GET', url) as response:
        if response.status_code == 404:
            raise MapRegionError(f"GeoNames has no {url.rsplit('/', 1)[-1]}")
        response.raise_for_status()
        received = 0
        with open(path, 'wb') as file:
            async for chunk in response.aiter_bytes():
                received += len(chunk)
                if received > max_bytes:
                    raise MapRegionError(f"GeoNames' {url.rsplit('/', 1)[-1]} is larger than {max_bytes} bytes")
                file.write(chunk)


async def _text(client: httpx.AsyncClient, url: str) -> str:
    response = await client.get(url)
    response.raise_for_status()
    return response.text


async def download_gazetteer(url: str, key: str, code: str | None, output: Path) -> int:
    """
    GeoNames' places for the place search, written to output as a gzipped TSV of GAZETTEER_COLUMNS: a country's (key
    its alpha-3 code, code its alpha-2) from its dump, or the world's (key 'world', no code) from cities1000, the
    places of 1,000 people or more, followed by the countries' simplified shapes. Returns the places written. The
    archives are downloaded beside output and deleted afterwards.
    """
    world = key == GAZETTEER_WORLD
    archive = output.with_name(f'.{output.name}.places.zip')
    shapes_archive = output.with_name(f'.{output.name}.shapes.zip')
    try:
        async with httpx.AsyncClient(timeout=120, follow_redirects=True, headers=HEADERS) as client:
            features = read_feature_labels(await _text(client, f'{url}/featureCodes_en.txt'))
            admin1 = read_names(await _text(client, f'{url}/admin1CodesASCII.txt'))
            admin2 = read_names(await _text(client, f'{url}/admin2Codes.txt'))
            await _download(client, f"{url}/{'cities1000' if world else code}.zip", archive)
            if world:
                await _download(client, f'{url}/shapes_simplified_low.json.zip', shapes_archive)
        shapes = await asyncio.to_thread(read_shapes, shapes_archive) if world else None
        member = 'cities1000.txt' if world else f'{code}.txt'
        # in a thread, so that the worker renews the job's lease meanwhile
        return await asyncio.to_thread(
            write_gazetteer, archive, member, output, None if world else code, admin1, admin2, features, shapes
        )
    except httpx.HTTPError as e:
        raise MapRegionError(f"GeoNames' places for {key} could not be downloaded: {type(e).__name__}")
    except (zipfile.BadZipFile, KeyError, UnicodeDecodeError, ValueError) as e:
        raise MapRegionError(f"GeoNames' places for {key} could not be read: {type(e).__name__}: {e}")
    finally:
        archive.unlink(missing_ok=True)
        shapes_archive.unlink(missing_ok=True)
