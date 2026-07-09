from abc import ABC, abstractmethod
from pathlib import Path
from asyncio import Queue
import hashlib
import aiofiles

from breedgraph.custom_exceptions import NoResultFoundError
from breedgraph.service_layer.infrastructure.driver import AbstractAsyncDriver
from breedgraph.domain.model.archive import (
    FileArchivalRecord, FileArchivalUpdate, ArchiveState, LocalState,
    ArchiveRequestor
)

from breedgraph.domain.events.archive import (
    ArchivalFailed,
    RetrievalSucceeded,
    RetrievalFailed
)
from breedgraph.config import FILE_STORAGE_PATH, ARCHIVE_ATTEMPT_LIMIT, RETRIEVE_ATTEMPT_LIMIT

from typing import AsyncGenerator

import logging

logger = logging.getLogger(__name__)

class AbstractFileArchivalService(ABC):
    """Abstract interface for file archival service implementations"""
    COLLECTION_TRANSITIONS = {
        ArchiveState.ARCHIVAL_PENDING: ArchiveState.ARCHIVING,
        ArchiveState.RETRIEVAL_PENDING: ArchiveState.RETRIEVING,
        ArchiveState.DELETION_PENDING: ArchiveState.DELETING,
        # For retries
        ArchiveState.ARCHIVING: ArchiveState.ARCHIVING,
        ArchiveState.RETRIEVING: ArchiveState.RETRIEVING,
        ArchiveState.DELETING: ArchiveState.DELETING,
    }

    def __init__(self, driver: AbstractAsyncDriver, queue: Queue):
        self.driver = driver
        self.queue = queue
        self.file_storage_path = Path(FILE_STORAGE_PATH)

    @abstractmethod
    async def create(self, record: FileArchivalRecord) -> FileArchivalRecord:
        """Create a new archival record"""
        ...

    @abstractmethod
    async def get(self, file_id: str) -> FileArchivalRecord:
        """Get an existing archival record"""
        ...

    @abstractmethod
    async def mark_accessed(self, file_id: str):
        """ Update the last accessed attribute """
        ...

    async def collect_for_archival(self, resume: bool = False) -> FileArchivalRecord | None:
        state = ArchiveState.ARCHIVING if resume else ArchiveState.ARCHIVAL_PENDING
        record = await self._collect_record(state)
        if record is None:
            return None
        elif record.attempts >= ARCHIVE_ATTEMPT_LIMIT:
            await self._set_state_values(
                record.file_id, archive_state=ArchiveState.ARCHIVAL_FAILED
            )
            await self.queue.put(
                ArchivalFailed(
                    file_id=record.file_id,
                    error_message=f"Failed to archive this file after {ARCHIVE_ATTEMPT_LIMIT} attempts"
                ))
            return await self.collect_for_archival()
        else:
            return record

    async def collect_for_retrieval(self, resume: bool = False) -> FileArchivalRecord | None:
        state = ArchiveState.RETRIEVING if resume else ArchiveState.RETRIEVAL_PENDING
        record = await self._collect_record(state)
        if record is None:
            return None
        elif record.attempts >= RETRIEVE_ATTEMPT_LIMIT:
            await self._set_state_values(
                record.file_id, archive_state=ArchiveState.RETRIEVAL_FAILED
            )
            await self.queue.put(
                RetrievalFailed(
                    file_id=record.file_id,
                    error_message=f"Failed to retrieve this file after {RETRIEVE_ATTEMPT_LIMIT} attempts"
                ))
            return await self.collect_for_retrieval()
        else:
            return record

    async def collect_for_deletion(self, resume: bool = False) -> FileArchivalRecord | None:
        state = ArchiveState.DELETING if resume else ArchiveState.DELETION_PENDING
        return await self._collect_record(state)

    async def _collect_record(self, state: ArchiveState) -> FileArchivalRecord|None:
        """Collect a single record marked as state and transition it to the valid transition state
        according to COLLECTION_TRANSITIONS
        Returns:
            FileArchivalRecord if a record was collected, None if no eligible records
        """
        ...

    async def update_archive_state(
            self,
            file_id: str,
            archive_state: ArchiveState
    ) -> FileArchivalRecord | None:
        """
        Update state for a record, return None only if record is deleted
        """
        logger.debug(f"Updating archival state for file {file_id}")
        if archive_state == ArchiveState.RETRIEVED:
            return await self.set_retrieved(file_id)
        elif archive_state == ArchiveState.DELETED:
            return await self.delete_record(file_id=file_id)

        # Support retry, in collect for retrieval and archival we check the attempts and escalate to raise fail events
        elif archive_state == ArchiveState.RETRIEVAL_FAILED:
            archive_state = ArchiveState.RETRIEVAL_PENDING
        elif archive_state == ArchiveState.ARCHIVAL_FAILED:
            archive_state = ArchiveState.ARCHIVAL_PENDING

        # reset attempt counter and last_attempt_at
        if archive_state in [ArchiveState.ARCHIVED, ArchiveState.RETRIEVED]:
            await self._clear_attempts(file_id)

        record = await self._set_state_values(
            file_id=file_id,
            archive_state=archive_state
        )
        return record

    async def update_local_state(self, file_id: str, local_state: LocalState) -> FileArchivalRecord:
        record = await self._set_state_values(file_id, local_state=local_state)
        return record

    async def set_retrieved(self, file_id: str) -> FileArchivalRecord:
        """
        This is a special case for state updates
         we additionally validate the hash matches the stored hash
         before accepting that the file is properly restored

        We also create events to eventually notify users that the file was restored or failed to be restored
        """
        file_hash = await self.get_hash(file_id)
        try:
            retrieved = await self._set_retrieved(file_id, file_hash)
        except NoResultFoundError:
            record = await self.update_archive_state(file_id, archive_state=ArchiveState.RETRIEVAL_FAILED)
            if record is None:
                raise ValueError("Record not found to update state after failed retrieval")
            return record
        else:
            await self.queue.put(RetrievalSucceeded(file_id=file_id))
            return retrieved

    @abstractmethod
    async def _set_retrieved(self, file_id: str, file_hash: str) -> FileArchivalRecord:
        """ Set as retrieved but match on file hash as well as file_id, set and return record if found
        If not found raise NoResultFoundError
        """
        ...

    @abstractmethod
    async def _clear_attempts(self, file_id: str) -> None:
        """ Set attempts to 0 and remove last_attempt_at"""
        ...

    @abstractmethod
    async def delete_record(self, file_id: str):
        """ Delete the archival record for the corresponding file_id """
        ...

    @abstractmethod
    async def _set_state_values(
            self,
            file_id: str,
            archive_state: ArchiveState | None = None,
            local_state: LocalState | None = None
    ):
        ...

    @abstractmethod
    async def add_requestor(self, file_id: str, user_id: int):
        """
        Add an ArchiveRequestor and update last_accessed
        """

    @abstractmethod
    def get_requestors(self, file_id: str) -> AsyncGenerator[ArchiveRequestor, None]:
        """
        Get ArchiveRequestors for the given file
        """
        ...

    @abstractmethod
    async def clear_requestors(self, file_id: str):
        """
        Clear the ArchiveRequestors for the given file
        """
        ...

    async def get_hash(self, file_id) -> str:
        file_path = Path(self.file_storage_path, file_id)
        hash_obj = hashlib.sha256()
        async with aiofiles.open(file_path, 'rb') as file:
            while chunk:= await file.read(8192):
                hash_obj.update(chunk)
        return hash_obj.hexdigest()

    @abstractmethod
    def get_expired_local(self) -> AsyncGenerator[FileArchivalRecord, None]:
        """
        Return file records that have expired locally
        """
        ...