import hashlib
import aiofiles
from pathlib import Path

from archive_worker.domain.model.archive import ArchiveState
from archive_worker.adapters.http.abstract_client import AbstractArchiveAPIClient

from typing import Dict, List, Any

CHUNK_SIZE = 1024*1024


class MockArchiveAPIClient(AbstractArchiveAPIClient):
    """Mock implementation of ArchiveAPIClient for testing

    This mock simulates the behavior of the ArchiveAPIClient including:
    - Writing files to disk during download
    - Calculating hashes of actual file content
    - Tracking all method calls for assertions
    """

    def __init__(self, file_content: bytes = b""):
        """Initialize mock with optional file content

        Args:
            file_content: Bytes to use when download_file is called
        """
        self.file_content = file_content
        self.call_history: Dict[str, List[Dict[str, Any]]] = {
            'download_file': [],
            'upload_file': [],
            'update_state': [],
            'get_archival_pending': [],
            'get_retrieval_pending': [],
            'get_deletion_pending': [],
            'get_archiving': [],
            'get_retrieving': [],
            'get_deleting': [],
        }
        # Exception control for testing error scenarios
        self._exceptions: Dict[str, Exception | None] = {
            'download_file': None,
            'upload_file': None,
            'update_state': None,
            'get_archival_pending': None,
            'get_retrieval_pending': None,
            'get_deletion_pending': None,
            'get_archiving': None,
            'get_retrieving': None,
            'get_deleting': None,
        }
        self.pending_archival = []
        self.archiving = []
        self.pending_retrieval = []
        self.retrieving = []
        self.pending_deletion = []
        self.deleting = []

    def set_exception(self, method: str, exception: Exception | None):
        """Set an exception to be raised for a specific method

        Args:
            method: Name of the method that should raise the exception
            exception: Exception instance to raise, or None to clear
        """
        if method not in self._exceptions:
            raise ValueError(f"Unknown method: {method}")
        self._exceptions[method] = exception

    async def download_file(self, file_id: str, destination: Path) -> str:
        """Download file to disk and return its hash

        Simulates real behavior by:
        1. Writing file_content to destination/file_id
        2. Calculating SHA256 hash of the written content
        3. Returning the hash

        Args:
            file_id: File identifier
            destination: Directory path to write file to

        Returns:
            SHA256 hash of file content
        """
        self.call_history['download_file'].append({
            'file_id': file_id,
            'destination': destination
        })

        file_path = destination / file_id
        file_path.write_bytes(self.file_content)

        # Calculate hash of actual written content
        file_hash = hashlib.sha256(self.file_content).hexdigest()

        if self._exceptions['download_file']:
            raise self._exceptions['download_file']

        return file_hash

    async def upload_file(self, file_id: str, source: Path) -> dict:
        """Mock upload file operation

        Args:
            file_id: File identifier
            source: Directory containing the file

        Returns:
            Success response dictionary
        """
        self.call_history['upload_file'].append({
            'file_id': file_id,
            'source': source
        })

        if not Path(source, file_id).exists():
            raise FileNotFoundError

        elif self._exceptions['upload_file']:
            raise self._exceptions['upload_file']

        return {"file_id": file_id, "status": "success"}

    async def update_state(self, file_id: str, update: dict) -> dict:
        """Mock archive state update

        Args:
            file_id: File identifier
            update: Dictionary with state update information

        Returns:
            Updated record dictionary
        """
        self.call_history['update_state'].append({
            'file_id': file_id,
            'update': update
        })

        if self._exceptions['update_state']:
            raise self._exceptions['update_state']

        if update.get('archive_state') == ArchiveState.ARCHIVED.value:
            self.archiving = [r for r in self.archiving if not r.get('file_id') == file_id]
        elif update.get('archive_state') == ArchiveState.RETRIEVED.value:
            self.retrieving = [r for r in self.retrieving if not r.get('file_id') == file_id]
        elif update.get('archive_state') == ArchiveState.DELETED.value:
            self.deleting = [r for r in self.deleting if not r.get('file_id') == file_id]

        return {"file_id": file_id, **update}

    async def get_archival_pending(self) -> dict | None:
        """Mock get archival pending files"""
        self.call_history['get_archival_pending'].append({})

        if self._exceptions['get_archival_pending']:
            raise self._exceptions['get_archival_pending']

        if self.pending_archival:
            record = self.pending_archival.pop()
            self.archiving.append(record)
            return record

        return None

    async def get_archiving(self) -> dict | None:
        """Mock get archiving (resumed) files"""
        self.call_history['get_archiving'].append({})

        if self._exceptions['get_archiving']:
            raise self._exceptions['get_archiving']

        if self.archiving:
            return self.archiving[-1]
        return None

    async def get_retrieval_pending(self) -> dict | None:
        """Mock get retrieval pending files"""
        self.call_history['get_retrieval_pending'].append({})

        if self._exceptions['get_retrieval_pending']:
            raise self._exceptions['get_retrieval_pending']

        if self.pending_retrieval:
            record = self.pending_retrieval.pop()
            self.retrieving.append(record)
            return record
        return None

    async def get_retrieving(self) -> dict | None:
        """Mock get retrieving (resumed) files"""
        self.call_history['get_retrieving'].append({})

        if self._exceptions['get_retrieving']:
            raise self._exceptions['get_retrieving']

        if self.retrieving:
            return self.retrieving[-1]
        return None

    async def get_deletion_pending(self) -> dict | None:
        """Mock get deletion pending files"""
        self.call_history['get_deletion_pending'].append({})

        if self._exceptions['get_deletion_pending']:
            raise self._exceptions['get_deletion_pending']

        if self.pending_deletion:
            record = self.pending_deletion.pop()
            self.deleting.append(record)
            return record
        return None

    async def get_deleting(self) -> dict | None:
        """Mock get deleting (resumed) files"""
        self.call_history['get_deleting'].append({})

        if self._exceptions['get_deleting']:
            raise self._exceptions['get_deleting']

        if self.deleting:
            return self.deleting[-1]
        return None

    async def close(self):
        """Mock close connection"""
        pass

    def assert_update_state_call(self, file_id: str, archive_state: ArchiveState):
        assert self.call_history.get('update_state')
        for call_args in self.call_history.get('update_state', []):
            assert call_args.get('file_id') == file_id
            assert call_args.get('update', {}).get('archive_state') == archive_state.value