from abc import ABC, abstractmethod

from map_worker.domain.job import MapJob, Extract


class UploadRefused(Exception):
    """The API refused an extract's file as it is (too short, too long, not PMTiles, no room): sending it again won't
    help"""


class AbstractMapAPIClient(ABC):
    """The API's routes for the map worker (breedgraph entrypoints/fastapi/map_jobs.py)"""

    @abstractmethod
    async def lease(self, lane: str) -> MapJob | None:
        """The next job of the lane, leased to this worker, or None if none is queued"""
        ...

    @abstractmethod
    async def renew(self, job: MapJob) -> bool:
        """Extend the lease; False when the API no longer holds the job for this worker (JobCancelled)"""
        ...

    @abstractmethod
    async def post_result(self, job: MapJob, result: dict) -> bool:
        """A quick job's result; False if the lease is no longer held"""
        ...

    @abstractmethod
    async def post_failure(self, job: MapJob, error: str) -> bool:
        ...

    @abstractmethod
    async def upload(self, job: MapJob, extract: Extract) -> bool:
        """
        An extract's file, with the build it was cut from; False if the lease is no longer held, UploadRefused if the
        API refused the file
        """
        ...

    async def close(self) -> None:
        pass
