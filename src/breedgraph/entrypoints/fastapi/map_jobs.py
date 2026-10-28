from pathlib import Path
from typing import Any

from fastapi import APIRouter, HTTPException, Request, Header, Depends
from fastapi.responses import Response
from pydantic import BaseModel

from breedgraph import config
from breedgraph.adapters.pmtiles.jobs import receive_result, receive_extract, LeaseNotHeld, BadUpload, NoSpace

import logging
logger = logging.getLogger(__name__)


"""
These endpoints should only be accessed by the map worker (map_worker), which fetches for the API what its map
regions need from the internet (adapters/pmtiles/jobs.py)
"""

LANES = ('quick', 'extract')


def verify_service_token(authorization: str = Header(None)):
    if not config.MAP_WORKER_AUTH_TOKEN or authorization != f"Bearer {config.MAP_WORKER_AUTH_TOKEN}":
        raise HTTPException(status_code=401, detail="Unauthorized service request")

router = APIRouter(prefix='/map_jobs', dependencies=[Depends(verify_service_token)])


class Lease(BaseModel):
    lease: str

class JobResult(Lease):
    result: dict[str, Any]

class JobFailure(Lease):
    error: str


def not_held() -> HTTPException:
    return HTTPException(status_code=409, detail="The lease for this job is not held")


@router.get('/next/{lane}')
async def lease_next_job(request: Request, lane: str):
    """The next queued job of the lane (quick or extract) with its lease, or 204 if none is queued"""
    if lane not in LANES:
        raise HTTPException(status_code=404, detail=f"No such lane: {lane}")
    leased = await request.app.bus.state_store.lease_map_job(lane, config.MAP_JOB_LEASE_SECONDS)
    if leased is None:
        return Response(status_code=204)
    kind, key, lease, payload = leased
    return {'kind': kind, 'key': key, 'lease': lease, 'lease_seconds': config.MAP_JOB_LEASE_SECONDS, 'payload': payload}


@router.post('/{kind}/{key}/renew')
async def renew_lease(request: Request, kind: str, key: str, body: Lease):
    if not await request.app.bus.state_store.renew_map_job(kind, key, body.lease, config.MAP_JOB_LEASE_SECONDS):
        raise not_held()
    return Response(status_code=204)


@router.post('/{kind}/{key}/result')
async def post_result(request: Request, kind: str, key: str, body: JobResult):
    """A quick job's result: Protomaps' builds, outlines (kept in MAP_BOUNDARIES_PATH) or a size"""
    try:
        await receive_result(
            request.app.bus.state_store, Path(config.MAP_BOUNDARIES_PATH), config.MAP_JOB_LEASE_SECONDS,
            kind, key, body.lease, body.result
        )
    except LeaseNotHeld:
        raise not_held()
    return Response(status_code=204)


@router.put('/extract/{key}/file')
async def upload_extract(
        request: Request,
        key: str,
        x_map_lease: str = Header(...),
        x_map_size: int = Header(...),
        x_map_build: str | None = Header(None),
        x_map_version: str | None = Header(None)
):
    """
    An extract's file, kept in MAP_TILES_PATH as it arrives and moved into place by the API's waiting process, with
    the build and version of the tiles it was cut from
    """
    try:
        await receive_extract(
            request.app.bus.state_store, Path(config.MAP_TILES_PATH), config.MAP_JOB_LEASE_SECONDS,
            key, x_map_lease, x_map_size, request.stream(), build=x_map_build, version=x_map_version
        )
    except LeaseNotHeld:
        raise not_held()
    except BadUpload as e:
        logger.error(f"Refused the map worker's extract of {key}: {e}")
        raise HTTPException(status_code=400, detail=str(e))
    except NoSpace as e:
        logger.error(f"No room for the map worker's extract of {key}: {e}")
        raise HTTPException(status_code=507, detail=f"Not enough disk space: {e}")
    return Response(status_code=204)


@router.post('/{kind}/{key}/failure')
async def post_failure(request: Request, kind: str, key: str, body: JobFailure):
    if not await request.app.bus.state_store.finish_map_job(kind, key, body.lease, error=body.error):
        raise not_held()
    return Response(status_code=204)
