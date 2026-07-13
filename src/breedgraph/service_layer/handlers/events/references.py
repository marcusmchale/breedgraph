from datetime import datetime

from breedgraph.domain import events

from ...infrastructure.notifications import email_templates
from breedgraph.domain.model.references import FileReferenceStored
from breedgraph.domain.model.archive import FileArchivalRecord, ArchiveState, LocalState

from breedgraph.service_layer.infrastructure import AbstractNotifications, AbstractUnitOfWorkFactory, \
    FileManagementService, AbstractFileArchivalService



from ..registry import handlers

import logging
logger = logging.getLogger(__name__)


async def mark_file_for_archival(
        self,
        file_id: str,
        file_size: int,
        file_hash: str
) -> None:
    """Create an archival record for a large file"""
    if not self.archival_service:
        logger.warning(f"Archival service not configured, cannot archive file {file_id}")
        return

    try:

        logger.info(f"File {file_id} marked for archival")
    except Exception as e:
        logger.exception(f"Failed to mark file {file_id} for archival: {e}")


@handlers.event_handler()
async def upload_completed(
        event: events.references.UploadCompleted,
        uow_factory: AbstractUnitOfWorkFactory,
        notifications: AbstractNotifications,
        file_management: FileManagementService,
        archival_service: AbstractFileArchivalService
):
    async with uow_factory.get_uow(user_id=event.user_id) as uow:
        reference: FileReferenceStored = await uow.repositories.references.get(reference_id=event.reference_id)
        if reference.file_id and not reference.file_id == event.uuid:
            # delete any old referenced file if it exists
            await file_management.delete_file(uuid=reference.file_id)
            # mark for deletion from the archive also
            await archival_service.update_archive_state(
                file_id=event.uuid,
                archive_state=ArchiveState.DELETION_PENDING
            )
        # update the reference to give it the file_id
        reference.file_id = event.uuid

        account = await uow.repositories.accounts.get(user_id=event.user_id)
        message = email_templates.FileUploadSuccess(
            account.user,
            filename=reference.filename,
            reference_id=reference.id
        )
        await notifications.send(
            [account.user],
            message
        )
        await uow.commit()

    # Prepare for archival
    record = FileArchivalRecord(
        file_id=event.uuid,
        file_size=event.file_size,
        file_hash=event.file_hash,
        last_accessed=datetime.now(),
        archive_state=ArchiveState.ARCHIVAL_PENDING,
        local_state=LocalState.LOCAL
    )
    await archival_service.create(record)


@handlers.event_handler()
async def upload_failed(
        event: events.references.UploadFailed,
        uow_factory: AbstractUnitOfWorkFactory,
        notifications: AbstractNotifications,
        file_management: FileManagementService
):
    # delete the failed file
    await file_management.delete_file(uuid=event.uuid)
    # and notify the user
    async with uow_factory.get_uow(user_id=event.user_id) as uow:
        reference: FileReferenceStored = await uow.repositories.references.get(reference_id=event.reference_id)

        account = await uow.repositories.accounts.get(user_id=event.user)
        message = email_templates.FileUploadFailed(
            account.user,
            filename=reference.filename,
            reference_id=reference.id
        )
        await notifications.send(
            [account.user],
            message
        )

@handlers.event_handler()
async def file_reference_deleted(
        event: events.references.FileReferenceDeleted,
        file_management: FileManagementService,
        archival_service: AbstractFileArchivalService
):
    await file_management.delete_file(uuid=event.uuid)

    await archival_service.update_archive_state(
        file_id=event.uuid,
        archive_state=ArchiveState.DELETION_PENDING
    )