from itsdangerous import URLSafeTimedSerializer
from datetime import datetime, timedelta
from dataclasses import asdict

from breedgraph.domain import events
from breedgraph.domain.model import FileReferenceBase
from breedgraph.service_layer.infrastructure import (
    AbstractNotifications,
    AbstractUnitOfWorkFactory,
    AbstractFileArchivalService
)
from ...infrastructure.notifications import email_templates

from breedgraph.config import FILE_DOWNLOAD_SALT, SECRET_KEY, get_download_endpoint, FILE_DOWNLOAD_EXPIRES

from ..registry import handlers

import logging

logger = logging.getLogger(__name__)


@handlers.event_handler()
async def archival_failed(
        event: events.archive.ArchivalFailed
):
    """Handle archival failure - log the error"""
    logger.error(f"Archival failed for file {event.file_id}: {event.error_message}")
    # todo consider who (if anyone) should be notified here.
    #  It is a concern for sysadmin rather than users, but shouldn't be ignored
    #  we may want to add a contact for sysadmin purposes to the configuration.


@handlers.event_handler()
async def retrieval_succeeded(
        event: events.archive.RetrievalSucceeded,
        archival_service: AbstractFileArchivalService,
        uow_factory: AbstractUnitOfWorkFactory,
        notifications: AbstractNotifications
):
    """Handle successful retrieval by notifying requesting users"""
    logger.info(f"Retrieval succeeded for file {event.file_id}")
    async for requestor in archival_service.get_requestors(event.file_id):
        try:
            # get reference associated with the file to include file name etc.
            # this is per request as the user may now only have restricted read access to the record
            async with uow_factory.get_uow(user_id=requestor.id) as uow:
                reference: FileReferenceBase = await uow.repositories.references.get(file_id=event.file_id)
                if reference is None:
                    logger.info(
                        f" File {event.file_id} was retrieved for user {requestor.id},"
                        " but they do not have access. This is "
                        " either because the file is no longer associated with a reference "
                        " or they no longer have read access "
                    )
                else:
                    file_details = {
                        'uuid': reference.file_id,
                        'filename': reference.filename,
                        'contentType': reference.content_type
                    }
                    token = URLSafeTimedSerializer(SECRET_KEY).dumps(
                        file_details,
                        salt=FILE_DOWNLOAD_SALT
                    )
                    message = email_templates.FileRetrievalSuccess(
                        requestor=requestor,
                        reference=reference,
                        url= f'{get_download_endpoint()}{token}',
                        expires=datetime.now() + timedelta(minutes=FILE_DOWNLOAD_EXPIRES)
                    )
                    await notifications.send([requestor], message)
                    logger.info(f"Sent retrieval success notification to user {requestor.id}")
        except Exception as e:
            logger.error(f"Failed to notify requestor {asdict(requestor)} of retrieval success: {e}")

@handlers.event_handler()
async def retrieval_failed(
        event: events.archive.RetrievalFailed,
        archival_service: AbstractFileArchivalService,
        notifications: AbstractNotifications
):
    """Handle retrieval failure - notify requesting users"""
    logger.error(f"Retrieval failed for file {event.file_id}: {event.error_message}")
    async for requestor in archival_service.get_requestors(event.file_id):
        try:
            message = email_templates.FileRetrievalFailed(
                requestor=requestor,
                file_id=event.file_id
            )
            await notifications.send([requestor], message)
            logger.info(f"Sent retrieval failure notification to user {asdict(requestor)}")
        except Exception as e:
            logger.error(f"Failed to notify requestor {asdict(requestor)} of retrieval failure: {e}")
