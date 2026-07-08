import logging
from pathlib import Path

from archive_worker.domain.model.archive import ArchiveState
from archive_worker.adapters.http.abstract_client import AbstractArchiveAPIClient

logger = logging.getLogger(__name__)


async def handle_archival(client: AbstractArchiveAPIClient, destination: Path, record: dict):
    """Handle archival of a file from web server to archive"""
    file_id = record['file_id']
    file_hash = record['file_hash']
    try:
        # Download file from web server
        logger.debug(f"Downloading {file_id} from web server")
        download_hash = await client.download_file(file_id, destination)
        if download_hash != file_hash:
            raise ValueError(f"Hash mismatch for {file_id}")
        logger.info(f"Successfully archived {file_id}")
        # Update state
        await client.update_state(file_id, {
            "archive_state": ArchiveState.ARCHIVED.value
        })
    except Exception as e:
        logger.error(f"Archival failed for {file_id}: {e}")
        await client.update_state(file_id, {
            "archive_state": ArchiveState.ARCHIVAL_FAILED.value
        })
        raise


async def handle_retrieval(client: AbstractArchiveAPIClient, destination: Path, record: dict):
    """Handle retrieval of a file from archive to web server"""
    file_id = record['file_id']

    try:
        # Upload to web server
        logger.debug(f"Uploading {file_id} to web server")
        await client.upload_file(file_id, destination)
        # Update state
        await client.update_state(file_id, {
            "archive_state": ArchiveState.RETRIEVED.value
        })

    except Exception as e:
        logger.error(f"Retrieval failed for {file_id}: {e}")
        await client.update_state(file_id, {
            "archive_state": ArchiveState.RETRIEVAL_FAILED.value
        })
        raise


async def handle_deletion(client: AbstractArchiveAPIClient, destination: Path, record: dict):
    """Handle deletion of a file from archive"""
    file_id = record['file_id']

    try:
        # Delete from archive storage
        logger.debug(f"Deleting {file_id} from archive")
        file_path = destination / file_id

        if file_path.exists():
            file_path.unlink()

        logger.info(f"Successfully deleted {file_id}")

        # Update state
        await client.update_state(file_id, {
            "archive_state": ArchiveState.DELETED.value
        })

    except Exception as e:
        logger.error(f"Deletion failed for {file_id}: {e}")
        await client.update_state(file_id, {
            "archive_state": ArchiveState.DELETION_FAILED.value
        })
        raise