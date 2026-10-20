from breedgraph import config
from breedgraph.domain import commands
from breedgraph.domain.model.archive import ArchiveState, LocalState, FileArchivalUpdate

from breedgraph.service_layer.infrastructure import (
    AbstractFileArchivalService, FileManagementService, AbstractUnitOfWorkFactory
)
from breedgraph.service_layer.application.file_deletion import delete_file_and_archive

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
async def remove_unused_file_references(
        cmd: commands.archive.RemoveUnusedFileReferences,
        uow_factory: AbstractUnitOfWorkFactory,
        archival_service: AbstractFileArchivalService,
        file_management: FileManagementService
):
    async with uow_factory.get_uow() as uow:
        file_ids = await uow.repositories.references.remove_unused_files(days=config.UNUSED_REFERENCE_RETENTION_DAYS)
        await uow.commit()
    logger.info(f"Removed unused file references, deleting their {len(file_ids)} files")
    # once no reference points to them
    for file_id in file_ids:
        try:
            await delete_file_and_archive(file_id, file_management, archival_service)
        except Exception as e:
            logger.error(f"Error deleting file {file_id} of an unused reference: {str(e)}")

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