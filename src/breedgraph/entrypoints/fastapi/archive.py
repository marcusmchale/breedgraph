from contextlib import aclosing
from pathlib import Path
import hashlib
import aiofiles

from fastapi import APIRouter, HTTPException, Request, Header, Depends
from fastapi.responses import Response, StreamingResponse

from breedgraph import config
from breedgraph.domain.model.archive import FileArchivalUpdate, ArchiveState
from breedgraph.adapters.files.age import AgeError, encrypted_chunks, decrypt_file, file_chunks

import logging
logger = logging.getLogger(__name__)


"""
These endpoints should only be accessed by the file archival server.
Files are encrypted on their way to it and decrypted on their way back, so it never holds a readable copy
(docs/backups.md, Encryption key).
"""

def verify_service_token(authorization: str = Header(None)):
    if authorization != f"Bearer {config.ARCHIVE_AUTH_TOKEN}":
        raise HTTPException(status_code=401, detail="Unauthorized service request")

def archive_encrypted() -> bool:
    """Whether files go to the archive server encrypted: always, except in development without a key"""
    if config.ENCRYPTION_RECIPIENT:
        return True
    if config.ENVIRONMENT is config.Environment.DEVELOPMENT:
        return False
    logger.error("ENCRYPTION_RECIPIENT is not set, so files cannot be sent to or received from the archive server")
    raise HTTPException(status_code=503, detail="Archive encryption not configured")

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
            archive_state=update.archive_state,
            archive_hash=update.archive_hash
        )
        if archive_record is None:  # deleted
            return {"file_id": file_id}

        if update.archive_state is ArchiveState.ARCHIVED and archive_record.archive_state is not ArchiveState.ARCHIVED:
            raise HTTPException(status_code=409, detail="The archived copy does not match what was sent")

        return {
            "file_id": archive_record.file_id,
            "file_size": archive_record.file_size,
            "file_hash": archive_record.file_hash
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.exception(f"Error updating record: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")

@router.get("/download/{file_id}")
async def download_file_to_archive(file_id: str, request: Request):
    """
    Send a file to the archive server, encrypted, and store the hash of what was sent,
    which the archive server reports back when it marks the file archived
    """
    archival_service = request.app.bus.archival_service
    if not archival_service:
        raise HTTPException(status_code=503, detail="Archival service not configured")

    file_path = Path(config.FILE_STORAGE_PATH, file_id)
    if not file_path.exists():
        raise HTTPException(status_code=404, detail="File not found")

    if archive_encrypted():
        source = encrypted_chunks(file_path, config.ENCRYPTION_RECIPIENT)
    else:
        source = file_chunks(file_path)

    async def send():
        sent = hashlib.sha256()
        async with aclosing(source) as chunks:
            async for chunk in chunks:
                sent.update(chunk)
                yield chunk
        # stored before the response ends, so before the archive server can report what it stored
        await archival_service.set_archive_hash(file_id, sent.hexdigest())

    return StreamingResponse(send(), media_type="application/octet-stream")

@router.put("/upload/{file_id}")
async def upload_file_to_restore(file_id: str, request: Request):
    """
    Receive a file back from the archive server and decrypt it.
    It is written beside its destination and put in place only once complete,
    so a failed retrieval leaves nothing behind. The file's hash is checked when the archive server marks it retrieved.
    """
    encrypted = archive_encrypted()
    if encrypted and not config.ENCRYPTION_IDENTITY_PATH:
        logger.error("ENCRYPTION_IDENTITY_PATH is not set, so archived files cannot be decrypted")
        raise HTTPException(status_code=503, detail="Archive encryption not configured")

    destination = Path(config.FILE_STORAGE_PATH, file_id)
    received = destination.with_name(f"{file_id}.received")
    decrypted = destination.with_name(f"{file_id}.decrypted")
    try:
        async with aiofiles.open(received, "wb") as f:
            async for chunk in request.stream():
                await f.write(chunk)

        if encrypted:
            await decrypt_file(received, decrypted, config.ENCRYPTION_IDENTITY_PATH)
            decrypted.replace(destination)
        else:
            received.replace(destination)

        return {"file_id": file_id}

    except AgeError as e:
        logger.error(str(e))
        raise HTTPException(status_code=400, detail="The file could not be decrypted")
    finally:
        received.unlink(missing_ok=True)
        decrypted.unlink(missing_ok=True)
