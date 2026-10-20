
from breedgraph.domain import events

from ...infrastructure.notifications import email_templates
from breedgraph.domain.model.references import FileReferenceStored
from breedgraph.domain.model.archive import FileArchivalRecord, ArchiveState, LocalState

from breedgraph.service_layer.infrastructure import AbstractNotifications, AbstractUnitOfWorkFactory, \
    FileManagementService, AbstractFileArchivalService
from breedgraph.service_layer.application.file_deletion import delete_file_and_archive



from ..registry import handlers

import logging
logger = logging.getLogger(__name__)


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
        replaced_file_id = reference.file_id if reference.file_id != event.uuid else None
        # update the reference to give it the file_id
        reference.file_id = event.uuid

        account = await uow.repositories.accounts.get(user_id=event.user_id)
        message = email_templates.FileUploadSuccess(
            account.user,
            filename=reference.filename,
            reference_id=reference.id
        )
        try:
            await notifications.send(
                [account.user],
                message
            )
        except Exception as e:
            logger.exception(f"Failed to send email notification for file upload success: {e}")

        await uow.commit()

    if replaced_file_id:
        # delete the replaced file, once the reference no longer points to it
        await delete_file_and_archive(replaced_file_id, file_management, archival_service)

    # Prepare for archival
    record = FileArchivalRecord(
        file_id=event.uuid,
        file_size=event.file_size,
        file_hash=event.file_hash,
        archive_state=ArchiveState.ARCHIVAL_PENDING,
        local_state=LocalState.LOCAL
    )
    logger.debug(f"File {event.uuid} marked for archival")
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

        account = await uow.repositories.accounts.get(user_id=event.user_id)
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
    await delete_file_and_archive(event.uuid, file_management, archival_service)