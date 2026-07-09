from breedgraph.domain import commands
from breedgraph.domain.model.archive import ArchiveState, LocalState, FileArchivalUpdate

from breedgraph.service_layer.infrastructure import AbstractFileArchivalService, FileManagementService

from ..registry import handlers

import logging
logger = logging.getLogger(__name__)

@handlers.command_handler()
async def request_file_restore(
        cmd: commands.archive.RequestFileRestore,
        archival_service: AbstractFileArchivalService
):
    record = await archival_service.get(cmd.file_id)
    if record.local_state == LocalState.LOCAL:
        return

    await archival_service.add_requestor(file_id=cmd.file_id, user_id=cmd.agent_id)
    if record.archive_state == ArchiveState.ARCHIVED:
        await archival_service.update_archive_state(
            file_id = cmd.file_id,
            archive_state=ArchiveState.RETRIEVAL_PENDING
        )

@handlers.command_handler()
async def trigger_file_retention_policy(
        cmd: commands.archive.TriggerFileRetentionPolicy,
        archival_service: AbstractFileArchivalService,
        file_management: FileManagementService
):
    to_delete = []
    async for record in archival_service.get_expired_local():
        if record.archive_state is ArchiveState.ARCHIVED:
                to_delete.append(record.file_id)
        else:
            logger.error(f"Not deleting local copy of file: {record.file_id}. This file is not archived")

    for file_id in to_delete:
        try:
            await archival_service.update_local_state(file_id=file_id, local_state=LocalState.EXPIRED)
            await file_management.delete_file(file_id)
            logger.debug(f"Deleted local copy of file: {file_id}")
        except Exception as e:
            logger.error(f'Error deleting local copy of file: {file_id}: {str(e)}')