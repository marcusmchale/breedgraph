import aiosmtplib

from typing import List
from src.breedgraph.domain.model.accounts import UserBase
from src.breedgraph.domain.services.email_templates import Email

from src.breedgraph.config import (
    MAIL_HOST,
    MAIL_PORT,
    MAIL_USERNAME,
    MAIL_PASSWORD,
    MAIL_USE_TLS
)
from src.breedgraph.service_layer.infrastructure import AbstractNotifications

class EmailNotifications(AbstractNotifications):

    @staticmethod
    async def send_to_unregistered(recipients: List[str], message: Email):
        await aiosmtplib.send(
            message.message,
            sender=f"{MAIL_USERNAME}@{MAIL_HOST}",
            recipients=recipients,
            hostname=f"smtp.{MAIL_HOST}",
            port=MAIL_PORT,
            username=MAIL_USERNAME,
            password=MAIL_PASSWORD,
            use_tls=MAIL_USE_TLS
        )

    @staticmethod
    async def send(recipients: List[UserBase], message: Email):
        await aiosmtplib.send(
            message.message,
            sender=f"{MAIL_USERNAME}@{MAIL_HOST}",
            recipients=[user.email for user in recipients],
            hostname=f"smtp.{MAIL_HOST}",
            port=MAIL_PORT,
            username=MAIL_USERNAME,
            password=MAIL_PASSWORD,
            use_tls=MAIL_USE_TLS
        )
