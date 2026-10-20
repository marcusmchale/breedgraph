from breedgraph.domain.model.archive import ArchiveState, LocalState
from breedgraph.service_layer.infrastructure import FileManagementService, AbstractFileArchivalService

import logging
logger = logging.getLogger(__name__)


async def delete_file_and_archive(
        file_id: str,
        file_management: FileManagementService,
        archival_service: AbstractFileArchivalService
):
    """Delete a file no reference points to any more: its local copy, and then its archived copy"""
    # as in the retention policy: the record must not describe a local copy once it is deleted
    await archival_service.update_local_state(file_id=file_id, local_state=LocalState.EXPIRED)
    await file_management.delete_file(uuid=file_id)
    # mark for deletion from the archive also
    logger.debug(f"File {file_id} marked for deletion")
    await archival_service.update_archive_state(
        file_id=file_id,
        archive_state=ArchiveState.DELETION_PENDING
    )
