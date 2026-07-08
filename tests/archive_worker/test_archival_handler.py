import pytest
import hashlib
from archive_worker.service_layer.handlers import (
    handle_archival,
    handle_retrieval,
    handle_deletion
)
from archive_worker.domain.model.archive import ArchiveState


@pytest.mark.asyncio
async def test_handle_archival_success(
        mock_api_client,
        temp_archive_dir,
        sample_file_content,
        sample_file_hash
):
    """Test successful file archival"""
    record: dict = {
        "file_id": "test-file-123",
        "file_size": len(sample_file_content),
        "file_hash": sample_file_hash
    }

    # Handle archival
    await handle_archival(mock_api_client, temp_archive_dir, record)

    # Verify file was saved
    saved_file = temp_archive_dir / "test-file-123"
    assert saved_file.exists()
    assert saved_file.read_bytes() == sample_file_content

    # Verify state update was called with success status
    mock_api_client.assert_update_state_call(
        file_id=record['file_id'],
        archive_state=ArchiveState.ARCHIVED
    )


@pytest.mark.asyncio
async def test_handle_archival_hash_mismatch(
        mock_api_client,
        temp_archive_dir,
        sample_file_content
):
    """Test archival fails on hash mismatch"""
    record: dict = {
        "file_id": "test-file-123",
        "file_size": len(sample_file_content),
        "file_hash": "wrong-hash-value"
    }

    # Should raise ValueError for hash mismatch
    with pytest.raises(ValueError, match="Hash mismatch"):
        await handle_archival(mock_api_client, temp_archive_dir, record)

    # Verify state is set for retry
    mock_api_client.assert_update_state_call(
        file_id=record['file_id'],
        archive_state=ArchiveState.ARCHIVAL_FAILED
    )


@pytest.mark.asyncio
async def test_handle_retrieval_success(
        mock_api_client,
        temp_archive_dir,
        sample_file_content
):
    """Test successful file retrieval"""
    # Create file in archive
    file_id = "test-file-456"
    file_path = temp_archive_dir / file_id
    file_path.write_bytes(sample_file_content)

    record = {
        "file_id": file_id,
        "file_size": len(sample_file_content),
        "file_hash": hashlib.sha256(sample_file_content).hexdigest()
    }

    # Handle retrieval
    await handle_retrieval(mock_api_client, temp_archive_dir, record)

    # Verify call to upload
    assert mock_api_client.call_history.get('upload_file',{})

    # Verify state update
    mock_api_client.assert_update_state_call(file_id=file_id, archive_state=ArchiveState.RETRIEVED)


@pytest.mark.asyncio
async def test_handle_retrieval_file_not_found(
        mock_api_client,
        temp_archive_dir
):
    """Test retrieval fails when file not in archive"""
    record: dict = {
        "file_id": "nonexistent-file",
        "file_size": 1024,
        "file_hash": "abc123"
    }

    # Should raise FileNotFoundError
    with pytest.raises(FileNotFoundError):
        await handle_retrieval(mock_api_client, temp_archive_dir, record)

    # Verify failure state update
    mock_api_client.assert_update_state_call(file_id=record['file_id'], archive_state=ArchiveState.RETRIEVAL_FAILED)

@pytest.mark.asyncio
async def test_handle_deletion_success(
        mock_api_client,
        temp_archive_dir,
        sample_file_content
):
    """Test successful file deletion"""
    # Create file in archive
    file_id = "test-file-delete"
    file_path = temp_archive_dir / file_id
    file_path.write_bytes(sample_file_content)

    record = {
        "file_id": file_id,
        "file_size": len(sample_file_content),
        "file_hash": hashlib.sha256(sample_file_content).hexdigest()
    }

    # Verify file exists before deletion
    assert file_path.exists()

    # Handle deletion
    await handle_deletion(mock_api_client, temp_archive_dir, record)

    # Verify file was deleted
    assert not file_path.exists()

@pytest.mark.asyncio
async def test_handle_deletion_file_not_found(
        mock_api_client,
        temp_archive_dir
):
    """Test deletion succeeds even if file not found"""
    record: dict = {
        "file_id": "nonexistent-delete",
        "file_size": 1024,
        "file_hash": "abc123"
    }

    # Should not raise exception (file already gone)
    await handle_deletion(mock_api_client, temp_archive_dir, record)

    # Verify state update was called
    mock_api_client.assert_update_state_call(file_id=record['file_id'], archive_state=ArchiveState.DELETED)
