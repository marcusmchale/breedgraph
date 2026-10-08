from typing import Any

from fastapi import APIRouter, HTTPException, Request, Header, Depends
from fastapi.responses import Response
from pydantic import BaseModel, Field

from breedgraph.config import ANALYSIS_WORKER_AUTH_TOKEN, ANALYSIS_JOB_LEASE_SECONDS
from breedgraph.domain.model.analysis import AnalysisType, AnalysisErrorCode, AnalysisWarningCode
from breedgraph.domain.services.analysis_job import to_jsonable

import logging
logger = logging.getLogger(__name__)


"""
These endpoints should only be accessed by the analysis worker
"""

def verify_service_token(authorization: str = Header(None)):
    if not ANALYSIS_WORKER_AUTH_TOKEN or authorization != f"Bearer {ANALYSIS_WORKER_AUTH_TOKEN}":
        raise HTTPException(status_code=401, detail="Unauthorized service request")

router = APIRouter(prefix='/analysis_jobs', dependencies=[Depends(verify_service_token)])


class ErrorMessage(BaseModel):
    code: AnalysisErrorCode
    message: str
    path: list[str] | None = None
    record_ids: list[int] | None = None

class WarningMessage(BaseModel):
    code: AnalysisWarningCode
    message: str
    path: list[str] | None = None
    record_ids: list[int] | None = None

class JobResult(BaseModel):
    lease: str
    analysis_id: str
    analysis_type: AnalysisType
    result: dict[str, Any]
    warnings: list[WarningMessage] = Field(default_factory=list)

class JobFailure(BaseModel):
    lease: str
    errors: list[ErrorMessage] = Field(min_length=1)
    warnings: list[WarningMessage] = Field(default_factory=list)


@router.get('/next')
async def lease_next_job(request: Request):
    """The next queued job with its lease, or 204 if none is queued."""
    leased = await request.app.bus.state_store.lease_analysis_job(ANALYSIS_JOB_LEASE_SECONDS)
    if leased is None:
        return Response(status_code=204)
    analysis_id, lease, payload = leased
    return {
        'analysis_id': analysis_id,
        'lease': lease,
        'lease_seconds': ANALYSIS_JOB_LEASE_SECONDS,
        'payload': payload
    }

@router.post('/{analysis_id}/result')
async def post_result(request: Request, analysis_id: str, body: JobResult):
    state_store = request.app.bus.state_store
    if body.analysis_id != analysis_id:
        raise HTTPException(status_code=422, detail="analysis_id does not match the path")
    if await state_store.get_analysis_type(analysis_id) != body.analysis_type.value:
        raise HTTPException(status_code=422, detail="analysis_type does not match the analysis")

    # NaN and inf become null
    result = to_jsonable(body.result) | {'analysis_id': analysis_id, 'analysis_type': body.analysis_type.value}
    completed = await state_store.complete_analysis_job(
        analysis_id,
        token=body.lease,
        result=result,
        warnings=[to_jsonable(w.model_dump()) for w in body.warnings]
    )
    if not completed:
        raise HTTPException(status_code=409, detail="The lease for this job is not held")
    return Response(status_code=204)

@router.post('/{analysis_id}/failure')
async def post_failure(request: Request, analysis_id: str, body: JobFailure):
    failed = await request.app.bus.state_store.fail_analysis_job(
        analysis_id,
        token=body.lease,
        errors=[to_jsonable(e.model_dump()) for e in body.errors],
        warnings=[to_jsonable(w.model_dump()) for w in body.warnings]
    )
    if not failed:
        raise HTTPException(status_code=409, detail="The lease for this job is not held")
    return Response(status_code=204)
