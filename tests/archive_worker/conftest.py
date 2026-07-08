import pytest
import tempfile
import hashlib
from pathlib import Path

from tests.archive_worker.mocks.mock_api_client import MockArchiveAPIClient

from archive_worker.service_layer.worker import ArchiveWorker


@pytest.fixture
def temp_archive_dir() -> Path:
    """Create a temporary archive directory"""
    with tempfile.TemporaryDirectory() as tmpdir:
        yield Path(tmpdir)

@pytest.fixture
def sample_file_content() -> bytes:
    """Create sample file content"""
    return b"This is a sample file content for testing archival operations."


@pytest.fixture
def sample_file_hash(sample_file_content: bytes) -> str:
    """Generate hash of sample file"""
    return hashlib.sha256(sample_file_content).hexdigest()


@pytest.fixture
def sample_archive_record(sample_file_hash: str) -> dict:
    """Create a sample archive record"""
    return {
        "file_id": "test-file-123",
        "file_size": 1024,
        "file_hash": sample_file_hash
    }


@pytest.fixture
def mock_api_client(sample_file_content: bytes) -> MockArchiveAPIClient:
    """Create a mock API client with realistic behavior

    The mock client:
    - Writes files to disk during download
    - Calculates correct hashes based on actual content
    - Tracks all method calls in call_history for assertions
    """
    return MockArchiveAPIClient(file_content=sample_file_content)


@pytest.fixture
def archive_worker(mock_api_client: MockArchiveAPIClient, temp_archive_dir) -> ArchiveWorker:
    """Create an ArchiveWorker instance"""
    worker = ArchiveWorker(
        client=mock_api_client,
        destination=temp_archive_dir,
        poll_interval=0.1  # Short interval for testing
    )
    return worker
