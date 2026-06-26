import logging

import aiofiles
import asyncio

from pathlib import Path
from fastapi import UploadFile, HTTPException

from breedgraph.service_layer.infrastructure.state_store import AbstractStateStore
from breedgraph.config import FILE_STORAGE_PATH, MAX_CONCURRENT_UPLOADS
from breedgraph.custom_exceptions import IllegalOperationError
from breedgraph.domain.model.submissions import SubmissionStatus

from typing import Callable

logger = logging.getLogger(__name__)

class FileManagementService:
    def __init__(self, state_store: AbstractStateStore):
        self.file_storage_path = Path(FILE_STORAGE_PATH)
        self.file_storage_path.mkdir(parents=True, exist_ok=True)
        self.state_store = state_store
        self.upload_semaphore = asyncio.Semaphore(MAX_CONCURRENT_UPLOADS)

    async def save_file(
            self, 
            uuid: str,
            file: UploadFile,
            on_complete: Callable | None = None,
            on_failed: Callable | None = None
    ):
        if not self.upload_semaphore.locked():
            logger.debug(f'Processing file for upload: {uuid}')
        else:
            logger.warning(f'Processing too many files for upload, rejecting: {uuid}')
            raise HTTPException(status_code=503, detail='Too many concurrent uploads')

        async with self.upload_semaphore:
            try:
                file_path = Path(self.file_storage_path, uuid)
                file_size = file.size
                logger.debug(f"Saving file {file.filename} with size {file_size} bytes as {uuid} ")
                await self.state_store.set_status(uuid, SubmissionStatus.PROCESSING)
                async with aiofiles.open(file_path, 'wb') as buffer:
                    bytes_written = 0
                    while chunk := await file.read(8192):
                        await buffer.write(chunk)
                        bytes_written += len(chunk)
                        progress = int((bytes_written/file_size) * 100)
                        await self.state_store.set_file_progress(uuid, progress)
                if on_complete:
                    await on_complete(uuid)
                await self.state_store.set_status(uuid, SubmissionStatus.COMPLETED)

            except Exception as e:
                logger.exception(f"Failed to save file {file.filename} with UUID {uuid}: {e}")
                await self.state_store.set_status(uuid, SubmissionStatus.FAILED)
                await self.state_store.set_errors(uuid, [str(e)])
                if on_failed:
                    await on_failed(uuid)

    async def delete_file(
            self,
            uuid: str
    ):
        if not uuid:
            raise ValueError("UUID cannot be empty")
        file_path = Path(self.file_storage_path, uuid)
        logger.debug(f"Deleting file {file_path}")

        if file_path.is_dir():
            # just another check to ensure pathlib isn't pointing at the file_storage_path still
            # this should all be protected at the file system level with write access only within the file_storage_path
            raise IllegalOperationError(f"Attempt to remove directory {file_path}, uuid supplied is empty string!")

        file_path.unlink(missing_ok=True)
