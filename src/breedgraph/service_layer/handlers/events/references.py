from itsdangerous import URLSafeTimedSerializer
from src.breedgraph import config

from src.breedgraph.domain import events
from src.breedgraph.custom_exceptions import (
    NoResultFoundError
)

from src.breedgraph.domain.services import email_templates
from src.breedgraph.domain.model.references import FileReferenceStored
from src.breedgraph.domain.model.accounts import UserOutput

from src.breedgraph.service_layer.infrastructure import AbstractNotifications, AbstractUnitOfWork, FileManagementService

from ..registry import handlers

import logging
logger = logging.getLogger(__name__)


@handlers.event_handler()
async def upload_completed(
        event: events.references.UploadCompleted,
        uow: AbstractUnitOfWork,
        notifications: AbstractNotifications
):
    async with uow.get_uow(user_id=event.user_id) as uow:
        reference: FileReferenceStored = await uow.repositories.references.get(event.reference_id)
        reference.uuid = event.uuid
        reference.filename = event.filename
        await uow.commit()

        account = await uow.repositories.accounts.get(user_id=event.user_id)
        message = email_templates.FileUploadSuccess(
            account.user,
            filename=event.filename,
            reference_id=event.reference_id
        )
        await notifications.send(
            [account.user],
            message
        )


@handlers.event_handler()
async def upload_failed(
        event: events.references.UploadFailed,
        uow: AbstractUnitOfWork,
        notifications: AbstractNotifications,
        file_management: FileManagementService
):
    # delete the failed file
    await file_management.delete_file(uuid=event.uuid)
    # and notify the user
    async with uow.get_uow(user_id=event.user_id) as uow:
        account = await uow.repositories.accounts.get(user_id=event.user)
        message = email_templates.FileUploadFailed(
            account.user,
            filename=event.filename,
            reference_id=event.reference_id
        )
        await notifications.send(
            [account.user],
            message
        )

@handlers.event_handler()
async def file_reference_deleted(
        event: events.references.FileReferenceDeleted,
        file_management: FileManagementService
):
    await file_management.delete_file(uuid=event.uuid)