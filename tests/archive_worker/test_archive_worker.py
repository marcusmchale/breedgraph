import pytest
import asyncio
from unittest.mock import AsyncMock, patch, call
from archive_worker.service_layer.worker import ArchiveWorker

@pytest.mark.asyncio
async def test_worker_initialization(mock_api_client, temp_archive_dir):
    """Test worker initializes correctly"""
    worker = ArchiveWorker(
        client=mock_api_client,
        destination=temp_archive_dir,
        poll_interval=5
    )

    assert worker.client == mock_api_client
    assert worker.destination == temp_archive_dir
    assert worker.poll_interval == 5
    assert temp_archive_dir.exists()

@pytest.mark.asyncio
async def test_worker_process_archival_no_files(archive_worker):
    """Test archival processing when no files pending"""
    await archive_worker._process_archival()
    assert len(archive_worker.client.call_history.get('get_archival_pending')) == 1

@pytest.mark.asyncio
async def test_worker_process_archival_with_file(
        archive_worker,
        sample_archive_record,
        sample_file_content
):
    """Test archival processing with pending file"""
    archive_worker.client.pending_archival.append(sample_archive_record)
    archive_worker.client.file_content = sample_file_content

    with patch('archive_worker.service_layer.worker.handle_archival') as mock_handler:
        await archive_worker._process_archival()
        assert len(archive_worker.client.call_history.get('get_archival_pending')) == 2
        mock_handler.assert_called_once()

@pytest.mark.asyncio
async def test_worker_process_archival_error_handling(archive_worker):
    """Test archival processing handles errors gracefully"""
    archive_worker.client.set_exception(
        'get_archival_pending',
        Exception("API error")
    )

    # Should not raise exception
    await archive_worker._process_archival()

    assert len(archive_worker.client.call_history['get_archival_pending']) == 1

@pytest.mark.asyncio
async def test_worker_process_retrieval_no_files(archive_worker):
    """Test retrieval processing when no files pending"""
    await archive_worker._process_retrieval()

    assert len(archive_worker.client.call_history['get_retrieval_pending']) == 1

@pytest.mark.asyncio
async def test_worker_process_retrieval_with_file(
        archive_worker,
        sample_archive_record,
        temp_archive_dir,
        sample_file_content
):
    """Test retrieval processing with pending file"""
    # Create file in archive
    file_path = temp_archive_dir / sample_archive_record["file_id"]
    file_path.write_bytes(sample_file_content)

    archive_worker.client.pending_retrieval.append(sample_archive_record)

    with patch('archive_worker.service_layer.worker.handle_retrieval') as mock_handler:
        await archive_worker._process_retrieval()

        assert len(archive_worker.client.call_history['get_retrieval_pending']) == 2
        mock_handler.assert_called_once()

@pytest.mark.asyncio
async def test_worker_process_retrieval_error_handling(archive_worker):
    """Test retrieval processing handles errors gracefully"""
    archive_worker.client.set_exception(
        'get_retrieval_pending',
        Exception("API error")
    )

    # Should not raise exception
    await archive_worker._process_retrieval()

    assert len(archive_worker.client.call_history['get_retrieval_pending']) == 1

@pytest.mark.asyncio
async def test_worker_process_deletion_no_files(archive_worker):
    """Test deletion processing when no files pending"""
    await archive_worker._process_deletion()

    assert len(archive_worker.client.call_history['get_deletion_pending']) == 1

@pytest.mark.asyncio
async def test_worker_process_deletion_with_file(
        archive_worker,
        sample_archive_record,
        temp_archive_dir,
        sample_file_content
):
    """Test deletion processing with pending file"""
    # Create file in archive
    file_path = temp_archive_dir / sample_archive_record["file_id"]
    file_path.write_bytes(sample_file_content)

    archive_worker.client.pending_deletion.append(sample_archive_record)

    with patch('archive_worker.service_layer.worker.handle_deletion') as mock_handler:
        await archive_worker._process_deletion()

        assert len(archive_worker.client.call_history['get_deletion_pending']) == 2
        mock_handler.assert_called_once()

@pytest.mark.asyncio
async def test_worker_process_deletion_error_handling(archive_worker):
    """Test deletion processing handles errors gracefully"""
    archive_worker.client.set_exception(
        'get_deletion_pending',
        Exception("API error")
    )
    # Should not raise exception
    await archive_worker._process_deletion()

    assert len(archive_worker.client.call_history['get_deletion_pending']) == 1

@pytest.mark.asyncio
async def test_worker_run_continues_on_error(
        archive_worker,
        sample_archive_record
):
    """Test worker continues polling after errors"""
    # First call raises error, second returns None
    archive_worker.client.set_exception(
        'get_archival_pending',
        Exception("API error")
    )

    run_task = asyncio.create_task(archive_worker.run())

    # Let it run through at least two cycles
    await asyncio.sleep(0.3)

    run_task.cancel()
    try:
        await run_task
    except asyncio.CancelledError:
        pass

    # Should have tried multiple times despite error
    assert len(archive_worker.client.call_history['get_archival_pending']) >= 2
