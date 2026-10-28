"""
The map worker's jobs (docs/maps.md). With config.MAP_WORKER, what PmtilesMapRegions and scripts/map_tiles.py would
fetch from the internet is fetched by the map worker (map_worker), on a server with internet access: Protomaps' list
of builds, geoBoundaries' outlines, and pmtiles' sizes and extracts. Each is a job in the state store, which the worker
leases over /map_jobs/ (entrypoints/fastapi/map_jobs.py) while the API waits for it.

The helpers here stand in for the three PmtilesMapRegions uses (GeoBoundaries, ProtomapsBuilds, PmtilesCommand), so
that everything else about regions is as when the API fetches them itself. Coordinates never go to the worker:
sections are still found here, from the outlines, and a job carries only a region's key, its outline (public), a
build and zooms.
"""
import asyncio
import json
import os
import shutil
import time
from pathlib import Path
from typing import AsyncIterator, List, Tuple

import aiofiles

from breedgraph.service_layer.infrastructure.state_store import AbstractStateStore
from map_worker.domain.job import BUILD, VERSION
from .boundaries import GeoBoundaries
from .command import PmtilesCommand, ProtomapsBuilds, MapRegionError
from .regions import REGIONS_DIRECTORY

import logging
logger = logging.getLogger(__name__)

POLL_SECONDS = 5
UNLEASED_WARNING_SECONDS = 600
WORLD = 'world'  # the key of the world file's size and extract, which have no outline
UPLOAD_SUFFIX = '.upload'
UPLOAD_KEEP_SECONDS = 86400  # an upload left by an interrupted request is deleted at the next start after this
PMTILES_MAGIC = b'PMTiles'


class MapJobs:
    """Queue a job, or join the one queued, and wait for the map worker to finish it"""

    def __init__(self, state_store: AbstractStateStore, poll_seconds: float = POLL_SECONDS):
        self.state_store = state_store
        self.poll_seconds = poll_seconds

    async def run(self, kind: str, key: str, payload: dict, reuse_done: bool = False) -> dict:
        """The job's result; MapRegionError if it failed or was cancelled (its country removed)"""
        await self.state_store.enqueue_map_job(kind, key, payload, reuse_done=reuse_done)
        warned = False
        while True:
            job = await self.state_store.get_map_job(kind, key)
            if job is None:
                raise MapRegionError(f"The map worker's {kind} job for {key} was cancelled")
            if job['state'] == 'done':
                return job['result']
            if job['state'] == 'failed':
                raise MapRegionError(f"The map worker's {kind} job for {key} failed: {job['error']}")
            if not warned and not job['leased'] and time.time() - job['queued_at'] > UNLEASED_WARNING_SECONDS:
                logger.warning(f"No map worker has taken the {kind} job for {key} in {UNLEASED_WARNING_SECONDS} s: is one running?")
                warned = True
            await asyncio.sleep(self.poll_seconds)

    async def take_file(self, kind: str, key: str, payload: dict, output: Path) -> dict:
        """
        Wait for a job whose result is a file (receive_file), and move the file to output, which is in the directory it
        is received into; returns the job's result. A done job whose file is still to be taken is joined, as by a
        process resumed after a restart, and one whose file is gone (taken already, or deleted as left too long) is
        asked for again.
        """
        while True:
            result = await self.run(kind, key, payload, reuse_done=True)
            upload = output.parent / result['file']
            if upload.exists():
                break
            logger.warning(f"The map worker's {kind} file for {key} is no longer in {output.parent}, so it is asked for again")
            await self.state_store.delete_map_job(kind, key)
        os.replace(upload, output)
        await self.state_store.delete_map_job(kind, key)
        for other in output.parent.glob(f'.{key}.*{UPLOAD_SUFFIX}'):
            other.unlink(missing_ok=True)
        return result


class WorkerBoundaries(GeoBoundaries):
    """The outlines the map worker downloads, which the API keeps as it receives them (receive_result)"""

    def __init__(self, path: Path, jobs: MapJobs):
        super().__init__(path)
        self.jobs = jobs

    async def _download(self, code: str, level: str, path: Path) -> None:
        await self.jobs.run('outlines', f'{code}-{level}', {'code': code, 'level': level})
        if not path.exists():
            raise MapRegionError(f"The {level} outlines for {code} from the map worker were not kept in {self.path}")


class WorkerBuilds(ProtomapsBuilds):
    """Protomaps' list of builds, as the map worker reads it"""

    def __init__(self, build: str, jobs: MapJobs):
        super().__init__(build)
        self.jobs = jobs

    async def _fetch_list(self) -> List[dict]:
        return (await self.jobs.run('builds', 'latest', {}))['builds']


class WorkerPmtiles(PmtilesCommand):
    """Sizes and extracts by the map worker's pmtiles; an extract's file comes back to the API (receive_extract)"""

    def __init__(self, jobs: MapJobs):
        super().__init__('')
        self.jobs = jobs

    def available(self) -> bool:
        return True

    @staticmethod
    def _payload(build: str, outline: Path | None, minzoom: int, maxzoom: int) -> dict:
        return {
            'outline': json.loads(outline.read_text()) if outline is not None else None,
            'build': build,
            'minzoom': minzoom,
            'maxzoom': maxzoom
        }

    async def size(self, build: str, outline: Path | None, minzoom: int, maxzoom: int, key: str | None = None) -> int:
        if key is None:
            raise ValueError("The map worker's jobs need the region's key")
        return int((await self.jobs.run('size', key, self._payload(build, outline, minzoom, maxzoom)))['size'])

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
    ) -> Tuple[str, str | None]:
        """
        Wait for the extract and move its file to output, which is in the directory it is received into. A done
        extract whose file is still to be taken is joined, as by a process resumed after a restart. Returns the build
        and version the file was cut from: an earlier build of the same version, when the worker kept the region
        (map_worker adapters/cache.py), unless fresh.
        """
        if key is None:
            raise ValueError("The map worker's jobs need the region's key")
        payload = self._payload(build, outline, minzoom, maxzoom) | {'version': version, 'fresh': fresh}
        result = await self.jobs.take_file('extract', key, payload, output)
        if result.get('build'):
            return result['build'], result.get('version')
        return build, version


def sources(
        state_store: AbstractStateStore,
        worker: bool,
        command: str,
        build: str,
        boundaries_path: Path,
        poll_seconds: float = POLL_SECONDS
) -> Tuple[PmtilesCommand, ProtomapsBuilds, GeoBoundaries]:
    """The pmtiles command, the builds and the outlines regions are fetched with: the API's own, or the map worker's"""
    if not worker:
        return PmtilesCommand(command), ProtomapsBuilds(build), GeoBoundaries(boundaries_path)
    jobs = MapJobs(state_store, poll_seconds)
    return WorkerPmtiles(jobs), WorkerBuilds(build, jobs), WorkerBoundaries(boundaries_path, jobs)


def sweep_uploads(*directories: Path) -> None:
    """Delete uploads left by requests interrupted long ago: one under way is renewed by its job, or retried"""
    for directory in directories:
        for path in directory.glob(f'.*{UPLOAD_SUFFIX}'):
            if time.time() - path.stat().st_mtime > UPLOAD_KEEP_SECONDS:
                path.unlink(missing_ok=True)


""" What the map worker sends back (entrypoints/fastapi/map_jobs.py) """


class LeaseNotHeld(Exception):
    """The job was cancelled, or its lease expired and went to another"""


class BadUpload(Exception):
    pass


class NoSpace(Exception):
    pass


async def receive_result(
        state_store: AbstractStateStore,
        boundaries_path: Path,
        lease_seconds: int,
        kind: str,
        key: str,
        lease: str,
        result: dict
) -> None:
    """
    Finish a quick job (builds, outlines or size) with its result. Outlines are kept in their files first, so that
    whoever waits finds them once the job is done. A result not as the job asks fails the job.
    """
    if not await state_store.renew_map_job(kind, key, lease, lease_seconds):
        raise LeaseNotHeld(f"{kind} {key}")
    try:
        if kind == 'builds':
            builds = result.get('builds')
            if not isinstance(builds, list) or not all(isinstance(b, dict) and 'key' in b for b in builds):
                raise MapRegionError("the builds are not a list of builds")
            result = {'builds': [{'key': b['key'], 'version': b.get('version')} for b in builds]}
        elif kind == 'outlines':
            code, level = key.split('-', 1)
            about, outlines = result.get('about'), result.get('outlines')
            if not isinstance(about, dict):
                raise MapRegionError("the outlines came without what geoBoundaries says of them")
            await asyncio.to_thread(GeoBoundaries(boundaries_path).save, code, level, about, outlines)
            result = {}
        elif kind == 'size':
            size = result.get('size')
            if not isinstance(size, int) or isinstance(size, bool) or size < 0:
                raise MapRegionError("the size is not a number of bytes")
            result = {'size': size}
        else:
            raise MapRegionError(f"a {kind} job has a file, not a result")
    except MapRegionError as e:
        if not await state_store.finish_map_job(kind, key, lease, error=f"The map worker sent a bad result: {e}"):
            raise LeaseNotHeld(f"{kind} {key}")
        return
    if not await state_store.finish_map_job(kind, key, lease, result=result):
        raise LeaseNotHeld(f"{kind} {key}")


async def receive_extract(
        state_store: AbstractStateStore,
        tiles_path: Path,
        lease_seconds: int,
        key: str,
        lease: str,
        size: int,
        chunks: AsyncIterator[bytes],
        build: str | None = None,
        version: str | None = None
) -> None:
    """
    Keep an extract's file as it arrives, beside where it is moved to (WorkerPmtiles.extract), and finish the job with
    it and the build and version it was cut from
    """
    if build is not None and not BUILD.fullmatch(build):
        raise BadUpload(f"not one of Protomaps' builds: {build!r}")
    if version and not VERSION.fullmatch(version):
        raise BadUpload(f"not a version of the tiles: {version!r}")
    directory = tiles_path if key == WORLD else tiles_path / REGIONS_DIRECTORY
    await receive_file(
        state_store, 'extract', key, lease, lease_seconds, directory, size, chunks, PMTILES_MAGIC, 'PMTiles file',
        extra={'build': build, 'version': version or None}
    )


async def receive_file(
        state_store: AbstractStateStore,
        kind: str,
        key: str,
        lease: str,
        lease_seconds: int,
        directory: Path,
        size: int,
        chunks: AsyncIterator[bytes],
        magic: bytes,
        what: str,
        extra: dict | None = None
) -> None:
    """
    Keep a job's file as it arrives, under a name the API makes from the job, in the directory it is taken from
    (MapJobs.take_file), and finish the job with it: the size announced, and a file starting as one of its kind does
    (magic). Deleted unless the job finishes with it.
    """
    if not await state_store.renew_map_job(kind, key, lease, lease_seconds):
        raise LeaseNotHeld(f"{kind} {key}")
    directory.mkdir(parents=True, exist_ok=True)
    if shutil.disk_usage(directory).free < size:
        raise NoSpace(f"{size} bytes needed and {shutil.disk_usage(directory).free} free")
    name = f'.{key}.{lease}{UPLOAD_SUFFIX}'
    path = directory / name
    finished = False
    try:
        received, head = 0, b''
        async with aiofiles.open(path, 'wb') as f:
            async for chunk in chunks:
                received += len(chunk)
                if received > size:
                    raise BadUpload(f"more than the {size} bytes announced")
                if len(head) < len(magic):
                    head += chunk[:len(magic) - len(head)]
                await f.write(chunk)
        if received != size:
            raise BadUpload(f"{received} bytes of the {size} announced")
        if head != magic:
            raise BadUpload(f"not a {what}")
        if not await state_store.finish_map_job(kind, key, lease, result={'file': name, 'size': size, **(extra or {})}):
            raise LeaseNotHeld(f"{kind} {key}")
        finished = True
    finally:
        if not finished:
            path.unlink(missing_ok=True)
