import aiosmtplib

from typing import List

from breedgraph.config import (
    MAIL_HOST,
    MAIL_PORT,
    MAIL_USERNAME,
    MAIL_PASSWORD,
    MAIL_USE_TLS,
    MAIL_AUTHENTICATED
)
from breedgraph.service_layer.infrastructure.notifications import AbstractNotifications, NotificationRecipient, Email

class EmailNotifications(AbstractNotifications):

    @staticmethod
    async def send_to_unregistered(recipients: List[str], message: Email):
            await aiosmtplib.send(
                message.message,
                sender=f"{MAIL_USERNAME}@{MAIL_HOST}",
                recipients=recipients,
                hostname=f"smtp.{MAIL_HOST}",
                port=MAIL_PORT,
                username=MAIL_USERNAME if MAIL_AUTHENTICATED else None,
                password=MAIL_PASSWORD if MAIL_AUTHENTICATED else None,
                use_tls=MAIL_USE_TLS if MAIL_AUTHENTICATED else False
            )


    @staticmethod
    async def send(recipients: List[NotificationRecipient], message: Email):
        await aiosmtplib.send(
            message.message,
            sender=f"{MAIL_USERNAME}@{MAIL_HOST}",
            recipients=[recipient.email for recipient in recipients],
            hostname=f"smtp.{MAIL_HOST}",
            port=MAIL_PORT,
            username=MAIL_USERNAME if MAIL_AUTHENTICATED else None,
            password=MAIL_PASSWORD if MAIL_AUTHENTICATED else None,
            use_tls=MAIL_USE_TLS if MAIL_AUTHENTICATED else False
        )
