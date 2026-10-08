import json
import math

import httpx
import logging

from analysis_worker.domain.model.job import AnalysisJob, Message
from .abstract_client import AbstractAnalysisAPIClient

logger = logging.getLogger(__name__)


def _finite(value):
    """NaN and inf are not valid JSON, report them as null"""
    if isinstance(value, dict):
        return {k: _finite(v) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return [_finite(v) for v in value]
    if isinstance(value, float) and not math.isfinite(value):
        return None
    return value


class AnalysisAPIClient(AbstractAnalysisAPIClient):
    """HTTP client for communicating with BreedGraph analysis jobs API"""

    def __init__(self, base_url: str, timeout: int = 60, auth_token: str | None = None):
        self.base_url = f"{base_url.rstrip('/')}/analysis_jobs"
        self.timeout = timeout
        self.auth_token = auth_token
        self.client = httpx.AsyncClient(timeout=timeout)

    def _get_headers(self) -> dict:
        headers = {"User-Agent": "AnalysisWorker/1.0"}
        if self.auth_token:
            headers["Authorization"] = f"Bearer {self.auth_token}"
        return headers

    async def lease_job(self) -> AnalysisJob | None:
        response = await self.client.get(f"{self.base_url}/next", headers=self._get_headers())
        if response.status_code == 204:
            return None
        response.raise_for_status()
        data = response.json()
        return AnalysisJob(
            analysis_id=data['analysis_id'],
            lease=data['lease'],
            lease_seconds=data['lease_seconds'],
            payload=data['payload']
        )

    async def _post(self, job: AnalysisJob, endpoint: str, body: dict) -> bool:
        response = await self.client.post(
            f"{self.base_url}/{job.analysis_id}/{endpoint}",
            headers=self._get_headers() | {"Content-Type": "application/json"},
            content=json.dumps(_finite(body), allow_nan=False)
        )
        if response.status_code == 409:
            logger.warning(f"Lease for analysis {job.analysis_id} is no longer held, {endpoint} discarded")
            return False
        response.raise_for_status()
        return True

    async def post_result(self, job: AnalysisJob, result: dict, warnings: list[Message]) -> bool:
        return await self._post(job, 'result', {
            'lease': job.lease,
            'analysis_id': job.analysis_id,
            'analysis_type': job.analysis_type,
            'result': result,
            'warnings': [w.model_dump() for w in warnings]
        })

    async def post_failure(self, job: AnalysisJob, errors: list[Message], warnings: list[Message]) -> bool:
        return await self._post(job, 'failure', {
            'lease': job.lease,
            'errors': [e.model_dump() for e in errors],
            'warnings': [w.model_dump() for w in warnings]
        })

    async def close(self):
        await self.client.aclose()
