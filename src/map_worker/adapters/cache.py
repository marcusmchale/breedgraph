"""
The extracts the map worker has cut, kept in MAP_CACHE_PATH and sent again when a job asks for one of them (breedgraph
README.md, Maps): a country removed and added again, or added on another site whose worker shares the cache, is not
cut again from Protomaps.

Each region is kept once, as <key>.pmtiles with a <key>.json saying what it was cut from. A job is sent it when it asks
for the same zooms and outline and the same major version of the tiles (the same build, when it pins one), however old
the build: OpenStreetMap changes little in the places mapped, and a job asking fresh (scripts/map_tiles.py --refresh)
cuts the region again, replacing it. Nothing is deleted but by hand. Workers sharing the cache take a lock per region,
so that one waits for another cutting the same and is then sent its file.
"""
import asyncio
import fcntl
import hashlib
import json
import os
from contextlib import asynccontextmanager
from datetime import datetime, timezone
from pathlib import Path

from map_worker.domain.job import MapJob, Extract

LOCK_POLL_SECONDS = 1


def outline_digest(outline: dict | None) -> str:
    return hashlib.sha256(json.dumps(outline, sort_keys=True, separators=(',', ':')).encode()).hexdigest()


def major(version: str | None) -> str | None:
    return version.split('.')[0] if version else None


class ExtractCache:

    def __init__(self, path: Path, poll_seconds: float = LOCK_POLL_SECONDS):
        self.path = path
        self.poll_seconds = poll_seconds

    def check(self, work_path: Path) -> None:
        """Make the cache, which must be on the work path's filesystem, so that a cut is moved into it whole"""
        self.path.mkdir(parents=True, exist_ok=True)
        if self.path.stat().st_dev != work_path.stat().st_dev:
            raise RuntimeError(
                f"The map cache ({self.path}) is not on the same filesystem as the work path ({work_path})"
            )

    def _file(self, key: str) -> Path:
        return self.path / f'{key}.pmtiles'

    def _sidecar(self, key: str) -> Path:
        return self.path / f'{key}.json'

    @asynccontextmanager
    async def holding(self, key: str):
        """Hold the region's lock, waiting while another worker holds it"""
        with open(self.path / f'.{key}.lock', 'a') as lock:
            while True:
                try:
                    fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
                    break
                except BlockingIOError:
                    await asyncio.sleep(self.poll_seconds)
            try:
                yield
            finally:
                fcntl.flock(lock, fcntl.LOCK_UN)

    def find(self, job: MapJob) -> Extract | None:
        """The region kept for the extract job, or None if there is none to send it, or it asks for a fresh one"""
        payload = job.payload
        try:
            about = json.loads(self._sidecar(job.key).read_text())
        except (OSError, ValueError):
            return None
        if payload.get('fresh') or not self._file(job.key).exists():
            return None
        if (about.get('minzoom'), about.get('maxzoom'), about.get('outline')) \
                != (payload['minzoom'], payload['maxzoom'], outline_digest(payload['outline'])):
            return None
        version = payload.get('version')
        if version is None:
            if about.get('build') != payload['build']:
                return None
        elif major(about.get('version')) != major(version):
            return None
        return Extract(self._file(job.key), about['build'], about.get('version'), temporary=False)

    def keep(self, job: MapJob, cut: Path) -> Extract:
        """Move the job's cut into the cache, replacing the region kept"""
        payload = job.payload
        sidecar = self._sidecar(job.key)
        sidecar.unlink(missing_ok=True)  # so that no sidecar describes the new file but its own
        os.replace(cut, self._file(job.key))
        partial = sidecar.with_name(f'.{sidecar.name}.partial')
        partial.write_text(json.dumps({
            'key': job.key,
            'build': payload['build'],
            'version': payload.get('version'),
            'minzoom': payload['minzoom'],
            'maxzoom': payload['maxzoom'],
            'outline': outline_digest(payload['outline']),
            'size': self._file(job.key).stat().st_size,
            'cut': datetime.now(timezone.utc).isoformat(timespec='seconds')
        }, indent=2))
        os.replace(partial, sidecar)
        return Extract(self._file(job.key), payload['build'], payload.get('version'), temporary=False)
