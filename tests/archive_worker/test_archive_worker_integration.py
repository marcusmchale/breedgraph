import pytest
import asyncio
from pathlib import Path
from archive_worker.service_layer.worker import ArchiveWorker
from archive_worker.adapters.http.client import ArchiveAPIClient
from archive_worker.domain.model.archive import ArchiveState, LocalState


class TestArchiveWorkerIntegration:
    """Integration tests for archive worker"""

    @pytest.mark.asyncio
    async def test_full_archival_workflow(
            self,
            mock_api_client,
            temp_archive_dir,
            sample_file_content,
            sample_file_hash
    ):
        """Test complete archival workflow"""
        file_id = "integration-test-file"
        record = {
            "file_id": file_id,
            "file_size": len(sample_file_content),
            "file_hash": sample_file_hash
        }

        # Setup mocks
        mock_api_client.pending_archival.append(record)
        mock_api_client.file_content = sample_file_content

        # Create worker and process one cycle
        worker = ArchiveWorker(
            client=mock_api_client,
            destination=temp_archive_dir,
            poll_interval=0.1
        )

        run_task = asyncio.create_task(worker.run())
        await asyncio.sleep(0.2)
        run_task.cancel()

        try:
            await run_task
        except asyncio.CancelledError:
            pass

        # Verify file was archived
        archived_file = temp_archive_dir / file_id
        assert archived_file.exists()
        assert archived_file.read_bytes() == sample_file_content

        # Verify state was updated
        mock_api_client.assert_update_state_call(file_id=file_id, archive_state=ArchiveState.ARCHIVED)

    @pytest.mark.asyncio
    async def test_full_retrieval_workflow(
            self,
            mock_api_client,
            temp_archive_dir,
            sample_file_content,
            sample_file_hash
    ):
        """Test complete retrieval workflow"""
        file_id = "integration-retrieve-file"

        # Pre-populate archive
        file_path = temp_archive_dir / file_id
        file_path.write_bytes(sample_file_content)

        record = {
            "file_id": file_id,
            "file_size": len(sample_file_content),
            "file_hash": sample_file_hash
        }

        # Setup mocks
        mock_api_client.pending_retrieval.append(record)

        # Create worker and process one cycle
        worker = ArchiveWorker(
            client=mock_api_client,
            destination=temp_archive_dir,
            poll_interval=0.1
        )

        run_task = asyncio.create_task(worker.run())
        await asyncio.sleep(0.2)
        run_task.cancel()

        try:
            await run_task
        except asyncio.CancelledError:
            pass

        # Verify upload was called
        assert len(mock_api_client.call_history['upload_file']) == 1

        # Verify state was updated
        mock_api_client.assert_update_state_call(file_id=file_id, archive_state=ArchiveState.RETRIEVED)

    @pytest.mark.asyncio
    async def test_full_deletion_workflow(
            self,
            mock_api_client,
            temp_archive_dir,
            sample_file_content,
            sample_file_hash
    ):
        """Test complete deletion workflow"""
        file_id = "integration-delete-file"

        # Pre-populate archive
        file_path = temp_archive_dir / file_id
        file_path.write_bytes(sample_file_content)

        record = {
            "file_id": file_id,
            "file_size": len(sample_file_content),
            "file_hash": sample_file_hash
        }

        # Setup mocks
        mock_api_client.pending_deletion.append(record)

        # Create worker and process one cycle
        worker = ArchiveWorker(
            client=mock_api_client,
            destination=temp_archive_dir,
            poll_interval=0.1
        )
        run_task = asyncio.create_task(worker.run())
        await asyncio.sleep(0.2)
        run_task.cancel()

        try:
            await run_task
        except asyncio.CancelledError:
            pass

        # Verify file was deleted
        assert not file_path.exists()

    @pytest.mark.asyncio
    async def test_worker_handles_mixed_operations(
            self,
            mock_api_client,
            temp_archive_dir,
            sample_file_content,
            sample_file_hash
    ):
        """Test worker handling multiple operation types"""
        # Create files for retrieval and deletion
        retrieve_file_id = "retrieve-me"
        delete_file_id = "delete-me"

        retrieve_path = temp_archive_dir / retrieve_file_id
        delete_path = temp_archive_dir / delete_file_id
        retrieve_path.write_bytes(sample_file_content)
        delete_path.write_bytes(sample_file_content)

        # Setup mocks for each operation type
        archive_record = {
            "file_id": "archive-me",
            "file_size": len(sample_file_content),
            "file_hash": sample_file_hash
        }
        retrieve_record = {
            "file_id": retrieve_file_id,
            "file_size": len(sample_file_content),
            "file_hash": sample_file_hash
        }
        delete_record = {
            "file_id": delete_file_id,
            "file_size": len(sample_file_content),
            "file_hash": sample_file_hash
        }

        mock_api_client.pending_archival.append(archive_record)
        mock_api_client.pending_retrieval.append(retrieve_record)
        mock_api_client.pending_deletion.append(delete_record)
        mock_api_client.file_content = sample_file_content

        # Create worker
        worker = ArchiveWorker(
            client=mock_api_client,
            destination=temp_archive_dir,
            poll_interval=0.1
        )

        run_task = asyncio.create_task(worker.run())
        await asyncio.sleep(0.2)
        run_task.cancel()

        try:
            await run_task
        except asyncio.CancelledError:
            pass

        # Verify all operations were processed
        assert len(mock_api_client.call_history['get_archival_pending'])  > 0
        assert len(mock_api_client.call_history['get_retrieval_pending'])  > 0
        assert len(mock_api_client.call_history['get_deletion_pending'])  > 0
