from fastapi import APIRouter, HTTPException, Request, Header, Depends

from breedgraph.domain.commands.archive import TriggerFileRetentionPolicy

from breedgraph.config import RETENTION_AUTH_TOKEN

import logging
logger = logging.getLogger(__name__)


"""
These endpoints should only be accessed by a cron job running on the web server
The idea is that hitting the /retention/run endpoint triggers enforcement of the policy.
This can be scheduled for a period of low activity but generally shouldn't interfere with anything.

"""

def verify_service_token(authorization: str = Header(None)):
    if authorization != f"Bearer {RETENTION_AUTH_TOKEN}":
        raise HTTPException(status_code=401, detail="Unauthorized service request")

router = APIRouter(prefix='/retention', dependencies=[Depends(verify_service_token)])

@router.post("/run")
async def run_file_cleanup(request: Request, reason:str):
    """
    Add the event file cleanup requested and return
    """
    logger.debug(f"Triggering cleanup for reason: {reason}")
    try:
        bus = request.app.bus
        await bus.handle(TriggerFileRetentionPolicy())
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

    return {"status": "completed"}
