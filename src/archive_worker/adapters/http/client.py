import aiofiles
import httpx
import hashlib
from pathlib import Path
from enum import Enum
import logging

from .abstract_client import AbstractArchiveAPIClient

logger = logging.getLogger(__name__)

CHUNK_SIZE = 1024 * 1024  # 1 MiB

class ArchiveEndpoint(Enum):
    ARCHIVAL_PENDING = "archival_pending"
    ARCHIVING = "archiving"
    RETRIEVAL_PENDING = "retrieval_pending"
    RETRIEVING = "retrieving"
    DELETION_PENDING = "deletion_pending"
    DELETING = "deleting"

class ArchiveAPIClient(AbstractArchiveAPIClient):
    """HTTP client for communicating with BreedGraph archive API"""

    def __init__(self, base_url: str, timeout: int = 30, auth_token: str|None = None):
        self.base_url = f"{base_url.rstrip('/')}/archive"
        self.timeout = timeout
        self.auth_token = auth_token
        self.client = httpx.AsyncClient(timeout=timeout)

    def _get_headers(self) -> dict:
        """Get request headers"""
        headers = {"User-Agent": "ArchiveWorker/1.0"}
        if self.auth_token:
            headers["Authorization"] = f"Bearer {self.auth_token}"
        return headers

    async def _get_record(self, endpoint: ArchiveEndpoint):
        """Get a record to process"""
        try:
            response = await self.client.get(
                f"{self.base_url}/{endpoint.value}",
                headers=self._get_headers()
            )
            if response.status_code == 204:
                return None  # No records
            response.raise_for_status()
            return response.json()
        except httpx.HTTPError as e:
            logger.error(f"Failed to get record: {e}")
            raise

    async def get_archival_pending(self) -> dict | None:
        """Get a file to archive from the web server"""
        return await self._get_record(endpoint=ArchiveEndpoint.ARCHIVAL_PENDING)

    async def get_archiving(self) -> dict|None:
        """Get a file marked as ARCHIVING from the web server to resume"""
        return await self._get_record(endpoint=ArchiveEndpoint.ARCHIVING)

    async def get_retrieval_pending(self) -> dict | None:
        """Get a file to retrieve from archive"""
        return await self._get_record(endpoint=ArchiveEndpoint.RETRIEVAL_PENDING)

    async def get_retrieving(self) -> dict|None:
        """Get a file marked as RETRIEVING to resume"""
        return await self._get_record(endpoint=ArchiveEndpoint.RETRIEVING)

    async def get_deletion_pending(self) -> dict | None:
        """Get a file to delete from archive"""
        return await self._get_record(endpoint=ArchiveEndpoint.DELETION_PENDING)

    async def get_deleting(self) -> dict|None:
        """Get a file marked as deleting to resume"""
        return await self._get_record(endpoint=ArchiveEndpoint.DELETING)

    async def download_file(self, file_id: str, destination: Path) -> str:
        # todo implement range request support on the archive/download page so can resume large files
        #  will need to handle resuming/restart of hash creation from partial download
        """Download a file from the web server to disk."""
        try:
            async with self.client.stream(
                    "GET",
                    f"{self.base_url}/download/{file_id}",
                    headers=self._get_headers(),
            ) as response:
                response.raise_for_status()
                # Calculate hash while writing
                hash_obj = hashlib.sha256()
                async with aiofiles.open(Path(destination, file_id), "wb") as f:
                    async for chunk in response.aiter_bytes(CHUNK_SIZE):
                        await f.write(chunk)
                        hash_obj.update(chunk)
                file_hash = hash_obj.hexdigest()
                return file_hash

        except httpx.HTTPError as e:
            logger.error(f"Failed to download file {file_id}: {e}")
            raise

    async def upload_file(self, file_id: str, source: Path) -> dict:
        # todo implement range request support on the archive/download page so can resume large files
        """Upload file to the web server."""
        try:
            if not Path(source, file_id).is_file():
                raise FileNotFoundError

            async def file_stream():
                async with aiofiles.open(Path(source, file_id), "rb") as f:
                    while chunk := await f.read(CHUNK_SIZE):
                        yield chunk

            response = await self.client.put(
                f"{self.base_url}/upload/{file_id}",
                content=file_stream(),
                headers={
                    **self._get_headers(),
                    "Content-Type": "application/octet-stream",
                },
            )

            response.raise_for_status()
            return response.json()

        except Exception as e:
            logger.error(f"Failed to upload file {file_id}: {e}")
            raise

    async def update_state(self, file_id: str, update: dict) -> dict:
        """Update file archival state"""
        try:
            response = await self.client.patch(
                f"{self.base_url}/update/{file_id}",
                json=update,
                headers=self._get_headers()
            )
            response.raise_for_status()
            return response.json()
        except httpx.HTTPError as e:
            logger.error(f"Failed to update state for {file_id}: {e}")
            raise

    async def close(self):
        """Close the HTTP client"""
        await self.client.aclose()