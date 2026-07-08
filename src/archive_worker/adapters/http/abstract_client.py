from abc import ABC, abstractmethod
from pathlib import Path


class AbstractArchiveAPIClient(ABC):
    """Abstract base class for Archive API client implementations"""

    @abstractmethod
    async def get_archival_pending(self) -> dict | None:
        """Get a file to archive from the web server"""
        ...

    @abstractmethod
    async def get_archiving(self) -> dict | None:
        """Get a file marked as ARCHIVING from the web server to resume"""
        ...

    @abstractmethod
    async def get_retrieval_pending(self) -> dict | None:
        """Get a file to retrieve from archive"""
        ...

    @abstractmethod
    async def get_retrieving(self) -> dict | None:
        """Get a file marked as RETRIEVING to resume"""
        ...

    @abstractmethod
    async def get_deletion_pending(self) -> dict | None:
        """Get a file to delete from archive"""
        ...

    @abstractmethod
    async def get_deleting(self) -> dict | None:
        """Get a file marked as deleting to resume"""
        ...

    @abstractmethod
    async def download_file(self, file_id: str, destination: Path) -> str:
        """Download a file from the web server to disk.

        Args:
            file_id: File identifier
            destination: Directory path to write file to

        Returns:
            SHA256 hash of the downloaded file
        """
        ...

    @abstractmethod
    async def upload_file(self, file_id: str, source: Path) -> dict:
        """Upload file to the web server.

        Args:
            file_id: File identifier
            source: Directory containing the file

        Returns:
            Response dictionary with upload status
        """
        ...

    @abstractmethod
    async def update_state(self, file_id: str, update: dict) -> dict:
        """Update file archival state.

        Args:
            file_id: File identifier
            update: Dictionary with state update information

        Returns:
            Updated record dictionary
        """
        ...

    @abstractmethod
    async def close(self):
        """Close the client connection"""
        ...
