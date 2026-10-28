"""
The map worker run in the tests' process (src/map_worker), its client calling what the API's routes call
(entrypoints/fastapi/map_jobs.py) rather than over HTTP: for test_map_regions.py and the tests of other jobs it does.
"""
import asyncio
from pathlib import Path

from breedgraph.adapters.pmtiles.jobs import (
    receive_result, receive_extract, receive_gazetteer, LeaseNotHeld, BadUpload, NoSpace
)
from map_worker.adapters.http.abstract_client import AbstractMapAPIClient, UploadRefused
from map_worker.domain.job import MapJob

LEASE_SECONDS = 1.5


class InProcessClient(AbstractMapAPIClient):
    """The map worker's client, calling what the API's routes call: results, failures, and each kind's files"""

    def __init__(self, state_store, boundaries: Path, tiles: Path, places: Path | None = None):
        self.state_store = state_store
        self.boundaries = boundaries
        self.tiles = tiles
        self.places = places  # where the place search's files are received
        self.payloads = []

    async def lease(self, lane):
        leased = await self.state_store.lease_map_job(lane, LEASE_SECONDS)
        if leased is None:
            return None
        kind, key, lease, payload = leased
        self.payloads.append((kind, key, payload))
        return MapJob(kind, key, lease, LEASE_SECONDS, payload)

    async def renew(self, job):
        return await self.state_store.renew_map_job(job.kind, job.key, job.lease, LEASE_SECONDS)

    async def post_result(self, job, result):
        try:
            await receive_result(self.state_store, self.boundaries, LEASE_SECONDS, job.kind, job.key, job.lease, result)
        except LeaseNotHeld:
            return False
        return True

    async def post_failure(self, job, error):
        return await self.state_store.finish_map_job(job.kind, job.key, job.lease, error=error)

    async def upload(self, job, extract):
        async def chunks():
            yield extract.path.read_bytes()
        size = extract.path.stat().st_size
        try:
            if job.kind == 'extract':
                await receive_extract(
                    self.state_store, self.tiles, LEASE_SECONDS, job.key, job.lease, size, chunks(),
                    build=extract.build, version=extract.version
                )
            elif job.kind == 'gazetteer' and self.places is not None:
                await receive_gazetteer(self.state_store, self.places, LEASE_SECONDS, job.key, job.lease, size, chunks())
            else:
                raise BadUpload(f"No file is sent for {job.kind} jobs")
        except LeaseNotHeld:
            return False
        except (BadUpload, NoSpace) as e:
            raise UploadRefused(str(e))
        return True


async def until(condition, seconds: float = 10):
    for _ in range(int(seconds / 0.05)):
        if condition():
            return
        await asyncio.sleep(0.05)
    raise TimeoutError("The condition was not met")
