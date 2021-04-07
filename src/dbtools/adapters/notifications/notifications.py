import abc

import aiosmtplib

from typing import List
from dbtools.domain.model.accounts import UserBase
from .emails import Email

from dbtools.config import MAIL_SERVER, MAIL_PORT, MAIL_USERNAME, MAIL_PASSWORD, MAIL_DEFAULT_SENDER


class AbstractNotifications(abc.ABC):

    @staticmethod
    @abc.abstractmethod
    async def send(
            recipients: List[UserBase],
            message: Email
    ):
        raise NotImplementedError


class EmailNotifications(AbstractNotifications):

    @staticmethod
    async def send_to_unregistered(recipients: List[str], message: Email):
        await aiosmtplib.send(
            message.message,
            sender=MAIL_DEFAULT_SENDER,
            recipients=recipients,
            hostname=MAIL_SERVER,
            port=MAIL_PORT,
            username=MAIL_USERNAME,
            password=MAIL_PASSWORD,
            use_tls=True
        )

    @staticmethod
    async def send(recipients: List[UserBase], message: Email):
        await aiosmtplib.send(
            message.message,
            sender=MAIL_DEFAULT_SENDER,
            recipients=[user.email for user in recipients],
            hostname=MAIL_SERVER,
            port=MAIL_PORT,
            username=MAIL_USERNAME,
            password=MAIL_PASSWORD,
            use_tls=True
        )
