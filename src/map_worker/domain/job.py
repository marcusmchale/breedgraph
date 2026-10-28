"""
A job the API gives the map worker (breedgraph adapters/pmtiles/jobs.py), and the checks it passes before the worker
acts on it: the worker fetches only what maps need, from Protomaps, geoBoundaries and GeoNames, whatever an API
asks.
"""
import re
from dataclasses import dataclass
from pathlib import Path

from map_worker.fetching import PROTOMAPS_BUILD_URL

LANES = ('quick', 'extract')  # an extract waits in a queue of its own, so a long one holds up no quick job
MAX_ZOOM = 15

_REGION = r'world|[A-Z]{3}(-ADM[12]-[A-Za-z0-9_-]+)?'
KEYS = {
    'builds': re.compile(r'latest'),
    'outlines': re.compile(r'[A-Z]{3}-ADM[012]'),
    'size': re.compile(_REGION),
    'extract': re.compile(_REGION),
    'gazetteer': re.compile(r'world|[A-Z]{3}'),  # GeoNames' places for a country (alpha-3), or the world's towns
}
COUNTRY_ALPHA2 = re.compile(r'[A-Z]{2}')  # GeoNames names a country's file by it
BUILD = re.compile(re.escape(PROTOMAPS_BUILD_URL) + r'[A-Za-z0-9._-]+\.pmtiles')
VERSION = re.compile(r'[A-Za-z0-9.+-]{1,32}')  # the tiles' version, as Protomaps' list of builds gives it


@dataclass
class MapJob:
    kind: str
    key: str
    lease: str
    lease_seconds: int
    payload: dict


@dataclass
class Extract:
    """
    A file sent back for a job, an extract's with the build and version of the tiles it was cut from: a temporary file
    is deleted once sent, one kept in the cache is not
    """
    path: Path
    build: str | None
    version: str | None
    temporary: bool = True


class JobCancelled(Exception):
    """The API no longer holds the job for this worker: its country was removed, or its lease went to another"""


class BadJob(Exception):
    """A job this worker refuses"""


def check(job: MapJob) -> None:
    """Raise BadJob unless the job is one the worker does, asking for what maps need and nothing else"""
    if job.kind not in KEYS:
        raise BadJob(f"no such kind of job: {job.kind!r}")
    if not KEYS[job.kind].fullmatch(job.key):
        raise BadJob(f"not a key for {job.kind}: {job.key!r}")
    payload = job.payload
    if job.kind == 'outlines':
        if f"{payload.get('code')}-{payload.get('level')}" != job.key:
            raise BadJob(f"the outlines asked for are not {job.key}'s")
    elif job.kind in ('size', 'extract'):
        if not isinstance(payload.get('build'), str) or not BUILD.fullmatch(payload['build']):
            raise BadJob(f"not one of Protomaps' builds: {payload.get('build')!r}")
        minzoom, maxzoom = payload.get('minzoom'), payload.get('maxzoom')
        if not all(isinstance(zoom, int) and not isinstance(zoom, bool) for zoom in (minzoom, maxzoom)) \
                or not 0 <= minzoom <= maxzoom <= MAX_ZOOM:
            raise BadJob(f"not zooms from 0 to {MAX_ZOOM}: {minzoom!r}, {maxzoom!r}")
        outline = payload.get('outline')
        if outline is None:
            if job.key != 'world':
                raise BadJob(f"{job.key} has no outline")
        elif not isinstance(outline, dict) or outline.get('type') != 'FeatureCollection' \
                or not isinstance(outline.get('features'), list) or not outline['features']:
            raise BadJob(f"the outline of {job.key} is not a FeatureCollection")
        version = payload.get('version')
        if version is not None and (not isinstance(version, str) or not VERSION.fullmatch(version)):
            raise BadJob(f"not a version of the tiles: {version!r}")
        if not isinstance(payload.get('fresh', False), bool):
            raise BadJob(f"fresh is not true or false: {payload['fresh']!r}")
    elif job.kind == 'gazetteer':
        asked = {'fresh'} if job.key == 'world' else {'code', 'fresh'}
        if not set(payload) <= asked:
            raise BadJob(f"a gazetteer job asks for no more than {sorted(asked)}: {sorted(payload)}")
        if job.key != 'world' and not (isinstance(payload.get('code'), str) and COUNTRY_ALPHA2.fullmatch(payload['code'])):
            raise BadJob(f"not a country's alpha-2 code: {payload.get('code')!r}")
        if not isinstance(payload.get('fresh', False), bool):
            raise BadJob(f"fresh is not true or false: {payload['fresh']!r}")
