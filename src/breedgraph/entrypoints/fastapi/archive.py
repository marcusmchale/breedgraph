from pathlib import Path
import aiofiles

from fastapi import APIRouter, HTTPException, Request, Header, Depends
from fastapi.responses import Response, FileResponse

from breedgraph.domain.model.archive import FileArchivalUpdate, ArchiveState

from breedgraph.config import ARCHIVE_AUTH_TOKEN, FILE_STORAGE_PATH

import logging
logger = logging.getLogger(__name__)


"""
These endpoints should only be accessed by the archival server
"""

def verify_service_token(authorization: str = Header(None)):
    if authorization != f"Bearer {ARCHIVE_AUTH_TOKEN}":
        raise HTTPException(status_code=401, detail="Unauthorized service request")

router = APIRouter(prefix='/archive', dependencies=[Depends(verify_service_token)])


async def get_by_state(request: Request, state: ArchiveState):
    try:
        bus = request.app.bus
        archival_service = bus.archival_service

        if not archival_service:
            raise HTTPException(
                status_code=503,
                detail="Archival service not configured"
            )

        if state == ArchiveState.ARCHIVAL_PENDING:
            archive_record = await archival_service.collect_for_archival()
        elif state == ArchiveState.ARCHIVING:
            archive_record = await archival_service.collect_for_archival(resume=True)
        elif state == ArchiveState.RETRIEVAL_PENDING:
            archive_record = await archival_service.collect_for_retrieval()
        elif state == ArchiveState.RETRIEVING:
            archive_record = await archival_service.collect_for_retrieval(resume=True)
        elif state == ArchiveState.DELETION_PENDING:
            archive_record = await archival_service.collect_for_deletion()
        elif state == ArchiveState.DELETING:
            archive_record = await archival_service.collect_for_deletion(resume=True)
        else:
            raise ValueError("This API only presents records for pending or active states")

        if archive_record is None:
            return Response(status_code=204)

        return {
            "file_id": archive_record.file_id,
            "file_size": archive_record.file_size,
            "file_hash": archive_record.file_hash
        }

    except Exception as e:
        logger.exception(f"Error retrieving archive record: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")

@router.get("/archival_pending")
async def get_archival_pending(request: Request):
    """Get a file_id to copy from the web server to the archive"""
    return await get_by_state(request, state=ArchiveState.ARCHIVAL_PENDING)

@router.get("/archiving")
async def get_archiving(request: Request):
    """Get a file_id to resume copying from the web server to the archive"""
    return await get_by_state(request, state=ArchiveState.ARCHIVING)

@router.get("/retrieval_pending")
async def get_retrieval_pending(request: Request):
    """Get a file_id to copy from the archive to the web server"""
    return await get_by_state(request, state=ArchiveState.RETRIEVAL_PENDING)

@router.get("/retrieving")
async def get_retrieving(request: Request):
    """Get a file_id to resume copying from the archive to the web server"""
    return await get_by_state(request, state=ArchiveState.RETRIEVING)

@router.get("/deletion_pending")
async def get_deletion_pening(request: Request):
    """Get a file_id to delete from the archive """
    return await get_by_state(request, state=ArchiveState.DELETION_PENDING)

@router.get("/deleting")
async def get_deleting(request: Request):
    """Get a file_id to resume deleting from the archive """
    return await get_by_state(request, state=ArchiveState.DELETING)

@router.patch("/update/{file_id}")
async def update_archive(file_id: str, update: FileArchivalUpdate, request: Request):
    """Update and archive record"""
    try:
        bus = request.app.bus
        archival_service = bus.archival_service

        if not archival_service:
            raise HTTPException(
                status_code=503,
                detail="Archival service not configured"
            )
        archive_record = await archival_service.update_archive_state(
            file_id=file_id,
            archive_state=update.archive_state
        )

        return {
            "file_id": archive_record.file_id,
            "file_size": archive_record.file_size,
            "file_hash": archive_record.file_hash
        }

    except Exception as e:
        logger.exception(f"Error updating record: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")

@router.get("/download/{file_id}")
async def download_file_to_archive(file_id: str):
    file_path = Path(FILE_STORAGE_PATH, file_id)
    if not file_path.exists():
        raise HTTPException(status_code=404, detail="File not found")
    return FileResponse(
        file_path,
        filename=file_id
    )

@router.put("/upload/{file_id}")
async def upload_file_to_restore(file_id: str, request: Request):
    destination = Path(FILE_STORAGE_PATH, file_id)

    try:
        async with aiofiles.open(destination, "wb") as f:
            async for chunk in request.stream():
                await f.write(chunk)

        return {"file_id": file_id}

    except Exception:
        if destination.exists():
            destination.unlink(missing_ok=True)
        raise
