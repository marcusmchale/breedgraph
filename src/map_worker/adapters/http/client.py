import json
import os

import aiofiles
import httpx

from map_worker.domain.job import MapJob, Extract
from .abstract_client import AbstractMapAPIClient, UploadRefused

import logging
logger = logging.getLogger(__name__)

CHUNK_SIZE = 1024 * 1024  # 1 MiB
# each step of an upload, a chunk sent or the answer awaited, may take this long; the whole may take hours
UPLOAD_TIMEOUT = httpx.Timeout(300)


class MapAPIClient(AbstractMapAPIClient):
    """HTTP client for the map jobs API"""

    def __init__(self, base_url: str, timeout: int = 60, auth_token: str | None = None):
        self.base_url = f"{base_url.rstrip('/')}/map_jobs"
        self.auth_token = auth_token
        self.client = httpx.AsyncClient(timeout=timeout)

    def _headers(self) -> dict:
        headers = {"User-Agent": "MapWorker/1.0"}
        if self.auth_token:
            headers["Authorization"] = f"Bearer {self.auth_token}"
        return headers

    async def lease(self, lane: str) -> MapJob | None:
        response = await self.client.get(f"{self.base_url}/next/{lane}", headers=self._headers())
        if response.status_code == 204:
            return None
        response.raise_for_status()
        data = response.json()
        return MapJob(
            kind=data['kind'],
            key=data['key'],
            lease=data['lease'],
            lease_seconds=data['lease_seconds'],
            payload=data['payload']
        )

    async def _post(self, job: MapJob, endpoint: str, body: dict) -> bool:
        response = await self.client.post(
            f"{self.base_url}/{job.kind}/{job.key}/{endpoint}",
            headers=self._headers() | {"Content-Type": "application/json"},
            content=json.dumps({'lease': job.lease, **body})
        )
        if response.status_code == 409:
            logger.info(f"The {job.kind} job for {job.key} is no longer leased to this worker: {endpoint} dropped")
            return False
        response.raise_for_status()
        return True

    async def renew(self, job: MapJob) -> bool:
        return await self._post(job, 'renew', {})

    async def post_result(self, job: MapJob, result: dict) -> bool:
        return await self._post(job, 'result', {'result': result})

    async def post_failure(self, job: MapJob, error: str) -> bool:
        return await self._post(job, 'failure', {'error': error})

    async def upload(self, job: MapJob, extract: Extract) -> bool:
        async with aiofiles.open(extract.path, 'rb') as f:
            async def chunks():
                while chunk := await f.read(CHUNK_SIZE):
                    yield chunk

            response = await self.client.put(
                f"{self.base_url}/{job.kind}/{job.key}/file",
                headers=self._headers() | {
                    "Content-Type": "application/octet-stream",
                    "X-Map-Lease": job.lease,
                    # the size of the file opened, which a worker sharing the cache may replace meanwhile
                    "X-Map-Size": str(os.fstat(f.fileno()).st_size),
                    "X-Map-Build": extract.build,
                    "X-Map-Version": extract.version or ''
                },
                content=chunks(),
                timeout=UPLOAD_TIMEOUT
            )
        if response.status_code == 409:
            logger.info(f"The extract of {job.key} is no longer leased to this worker: its file is dropped")
            return False
        if response.status_code in (400, 507):
            try:
                detail = response.json().get('detail')
            except ValueError:
                detail = None
            raise UploadRefused(detail or response.text)
        response.raise_for_status()
        return True

    async def close(self) -> None:
        await self.client.aclose()
