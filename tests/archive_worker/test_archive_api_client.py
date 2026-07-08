import pytest
import httpx
from pathlib import Path
import hashlib

from unittest.mock import AsyncMock, MagicMock, patch
from archive_worker.adapters.http.client import ArchiveAPIClient

from archive_worker.config import ARCHIVE_DESTINATION

@pytest.fixture
def client():
    """Create client instance"""
    return ArchiveAPIClient(base_url="http://localhost:8000", timeout=30)

@pytest.fixture
def destination():
    return Path(ARCHIVE_DESTINATION)

@pytest.mark.asyncio
async def test_client_initialization(client):
    """Test client initializes correctly"""
    assert client.base_url == "http://localhost:8000/archive"
    assert client.timeout == 30
    assert client.auth_token is None

@pytest.mark.asyncio
async def test_client_with_auth_token():
    """Test client with auth token"""
    client = ArchiveAPIClient(
        base_url="http://localhost:8000",
        auth_token="test-token-123"
    )
    assert client.auth_token == "test-token-123"

@pytest.mark.asyncio
async def test_get_headers_without_token(client):
    """Test header generation without auth token"""
    headers = client._get_headers()
    assert "User-Agent" in headers
    assert headers["User-Agent"] == "ArchiveWorker/1.0"
    assert "Authorization" not in headers

@pytest.mark.asyncio
async def test_get_headers_with_token():
    """Test header generation with auth token"""
    client = ArchiveAPIClient(
        base_url="http://localhost:8000",
        auth_token="test-token"
    )
    headers = client._get_headers()
    assert headers["Authorization"] == "Bearer test-token"

@pytest.mark.asyncio
async def test_get_to_archive_no_files(client):
    """Test get_to_archive when no files pending"""
    with patch.object(client.client, 'get', new_callable=AsyncMock) as mock_get:
        mock_response = MagicMock()
        mock_response.status_code = 204
        mock_get.return_value = mock_response
        result = await client.get_archival_pending()
        assert result is None
        mock_get.assert_called_once()

@pytest.mark.asyncio
async def test_get_to_archive_with_file(client):
    """Test get_to_archive returns file record"""
    expected_record = {
        "file_id": "file-123",
        "file_size": 2048,
        "file_hash": "abc123def456"
    }

    with patch.object(client.client, 'get', new_callable=AsyncMock) as mock_get:
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = expected_record
        mock_get.return_value = mock_response
        result = await client.get_archival_pending()
        assert result == expected_record
        mock_get.assert_called_once()

@pytest.mark.asyncio
async def test_get_to_archive_http_error(client):
    """Test get_to_archive handles HTTP errors"""
    with patch.object(client.client, 'get', new_callable=AsyncMock) as mock_get:
        mock_get.side_effect = httpx.HTTPError("Connection failed")

        with pytest.raises(httpx.HTTPError):
            await client.get_archival_pending()

@pytest.mark.asyncio
async def test_get_to_retrieve_no_files(client):
    """Test get_to_retrieve when no files pending"""
    with patch.object(client.client, 'get', new_callable=AsyncMock) as mock_get:
        mock_response = MagicMock()
        mock_response.status_code = 204
        mock_get.return_value = mock_response

        result = await client.get_retrieval_pending()

        assert result is None

@pytest.mark.asyncio
async def test_get_to_retrieve_with_file(client):
    """Test get_to_retrieve returns file record"""
    expected_record = {
        "file_id": "file-456",
        "file_size": 4096,
        "file_hash": "xyz789"
    }

    with patch.object(client.client, 'get', new_callable=AsyncMock) as mock_get:
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = expected_record
        mock_get.return_value = mock_response

        result = await client.get_retrieval_pending()

        assert result == expected_record

@pytest.mark.asyncio
async def test_get_to_delete_no_files(client):
    """Test get_to_delete when no files pending"""
    with patch.object(client.client, 'get', new_callable=AsyncMock) as mock_get:
        mock_response = MagicMock()
        mock_response.status_code = 204
        mock_get.return_value = mock_response

        result = await client.get_deletion_pending()

        assert result is None

@pytest.mark.asyncio
async def test_get_to_delete_with_file(client):
    """Test get_to_delete returns file record"""
    expected_record = {
        "file_id": "file-789",
        "file_size": 8192,
        "file_hash": "hash123"
    }

    with patch.object(client.client, 'get', new_callable=AsyncMock) as mock_get:
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = expected_record
        mock_get.return_value = mock_response

        result = await client.get_deletion_pending()

        assert result == expected_record


from contextlib import asynccontextmanager


@pytest.mark.asyncio
async def test_download_file_success(client, sample_file_content, destination):
    """Test successful file download"""
    mock_response = AsyncMock()
    mock_response.status_code = 200
    mock_response.raise_for_status = MagicMock()

    # Mock aiter_bytes to yield content in chunks
    async def async_chunk_generator():
        chunk_size = 1024
        for i in range(0, len(sample_file_content), chunk_size):
            yield sample_file_content[i:i + chunk_size]

    mock_response.aiter_bytes = MagicMock(return_value=async_chunk_generator())

    # Create async context manager
    @asynccontextmanager
    async def mock_stream_context(*args, **kwargs):
        yield mock_response

    with patch.object(client.client, 'stream', side_effect=mock_stream_context):
        result = await client.download_file("file-123", destination)

        # Verify the file was written
        assert (destination / "file-123").exists()
        assert (destination / "file-123").read_bytes() == sample_file_content
        # Verify hash matches
        import hashlib
        expected_hash = hashlib.sha256(sample_file_content).hexdigest()
        assert result == expected_hash


@pytest.mark.asyncio
async def test_download_file_not_found(client, destination):
    """Test download file when not found"""
    mock_response = AsyncMock()
    mock_response.status_code = 404
    mock_response.raise_for_status = MagicMock(
        side_effect=httpx.HTTPStatusError(
            "Not Found", request=MagicMock(), response=mock_response
        )
    )

    # Create async context manager
    @asynccontextmanager
    async def mock_stream_context(*args, **kwargs):
        yield mock_response

    with patch.object(client.client, 'stream', side_effect=mock_stream_context):
        with pytest.raises(httpx.HTTPError):
            await client.download_file("nonexistent", destination)


@pytest.mark.asyncio
async def test_upload_file_success(client, temp_archive_dir, sample_file_content):
    """Test successful file upload"""
    # Create test file
    test_file = temp_archive_dir / "test-file"
    test_file.write_bytes(sample_file_content)

    with patch.object(client.client, 'put', new_callable=AsyncMock) as mock_post:
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"status": "success"}
        mock_post.return_value = mock_response

        result = await client.upload_file("test-file", temp_archive_dir)

        assert result == {"status": "success"}
        mock_post.assert_called_once()

@pytest.mark.asyncio
async def test_upload_file_not_found(client):
    """Test upload when file doesn't exist"""
    with pytest.raises(FileNotFoundError):
        await client.upload_file("file-123", Path("/nonexistent/path"))

@pytest.mark.asyncio
async def test_update_state_success(client):
    """Test successful state update"""
    update_data = {"archive_state": "ARCHIVED"}

    with patch.object(client.client, 'patch', new_callable=AsyncMock) as mock_patch:
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"file_id": "file-123", **update_data}
        mock_patch.return_value = mock_response

        result = await client.update_state("file-123", update_data)

        assert result["archive_state"] == "ARCHIVED"
        mock_patch.assert_called_once()

@pytest.mark.asyncio
async def test_update_state_failure(client):
    """Test state update failure"""
    with patch.object(client.client, 'patch', new_callable=AsyncMock) as mock_patch:
        mock_response = MagicMock()
        mock_response.status_code = 500
        mock_response.raise_for_status = MagicMock(
            side_effect=httpx.HTTPStatusError(
                "Server Error", request=MagicMock(), response=mock_response
            )
        )
        mock_patch.return_value = mock_response

        with pytest.raises(httpx.HTTPError):
            await client.update_state("file-123", {})

@pytest.mark.asyncio
async def test_close_client(client):
    """Test closing the client"""
    client.client.aclose = AsyncMock()
    await client.close()
    client.client.aclose.assert_called_once()
