import aiosmtplib
import logging
from typing import List

from breedgraph.config import (
    MAIL_HOST,
    MAIL_PORT,
    MAIL_FROM,
    MAIL_USERNAME,
    MAIL_PASSWORD,
    MAIL_USE_TLS,
    MAIL_AUTHENTICATED
)
from breedgraph.service_layer.infrastructure.notifications import AbstractNotifications, NotificationRecipient, Email

logger=logging.getLogger(__name__)

class EmailNotifications(AbstractNotifications):

    @staticmethod
    async def send_to_unregistered(recipients: List[str], message: Email):
        try:
            await aiosmtplib.send(
                message.message,
                sender=MAIL_FROM,
                recipients=recipients,
                hostname=MAIL_HOST,
                port=MAIL_PORT,
                username=MAIL_USERNAME if MAIL_AUTHENTICATED else None,
                password=MAIL_PASSWORD if MAIL_AUTHENTICATED else None,
                use_tls=MAIL_USE_TLS if MAIL_AUTHENTICATED else False,
                start_tls=MAIL_USE_TLS if MAIL_AUTHENTICATED else False
            )
        except Exception as e:
            logger.error(f"Failed to send email: {type(e).__name__, e}")


    @staticmethod
    async def send(recipients: List[NotificationRecipient], message: Email):
        try:
            await aiosmtplib.send(
                message.message,
                sender=MAIL_FROM,
                recipients=[recipient.email for recipient in recipients],
                hostname=MAIL_HOST,
                port=MAIL_PORT,
                username=MAIL_USERNAME if MAIL_AUTHENTICATED else None,
                password=MAIL_PASSWORD if MAIL_AUTHENTICATED else None,
                use_tls=MAIL_USE_TLS if MAIL_AUTHENTICATED else False,
                start_tls=MAIL_USE_TLS if MAIL_AUTHENTICATED else False
            )
        except Exception as e:
            logger.error(f"Failed to send email: {type(e).__name__, e}")