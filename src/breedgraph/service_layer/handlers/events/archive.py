from breedgraph.domain import events
from breedgraph.domain.model import FileReferenceBase
from breedgraph.service_layer.infrastructure import (
    AbstractNotifications,
    AbstractUnitOfWorkFactory,
    AbstractFileArchivalService
)
from ...infrastructure.notifications import email_templates

from breedgraph.config import LOCAL_STORAGE_DURATION

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
    """
    Handle successful retrieval by notifying requesting users. The email sends them to the site rather than to the file,
    as downloads are issued by the API, which checks the licences of the data citing the file (docs/licences.md §5).
    """
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
                    message = email_templates.FileRetrievalSuccess(
                        requestor=requestor,
                        reference=reference,
                        days=LOCAL_STORAGE_DURATION
                    )
                    await notifications.send([requestor], message)
                    logger.info(f"Sent retrieval success notification to user {requestor.id}")
        except Exception as e:
            logger.error(f"Failed to notify requestor {requestor.id} of retrieval success: {e}")
    # the requests are met, so a later retrieval of the file tells only those who ask for it again
    await archival_service.clear_requestors(event.file_id)

@handlers.event_handler()
async def retrieval_failed(
        event: events.archive.RetrievalFailed,
        archival_service: AbstractFileArchivalService,
        notifications: AbstractNotifications
):
    """
    Handle retrieval failure - notify requesting users. Their requests are kept, so they hear if the file is retrieved
    after all.
    """
    logger.error(f"Retrieval failed for file {event.file_id}: {event.error_message}")
    async for requestor in archival_service.get_requestors(event.file_id):
        try:
            message = email_templates.FileRetrievalFailed(
                requestor=requestor,
                file_id=event.file_id,
                error=event.error_message
            )
            await notifications.send([requestor], message)
            logger.info(f"Sent retrieval failure notification to user {requestor.id}")
        except Exception as e:
            logger.error(f"Failed to notify requestor {requestor.id} of retrieval failure: {e}")
