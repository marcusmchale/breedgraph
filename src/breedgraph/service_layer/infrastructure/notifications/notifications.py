import abc
from typing import List

from .email_templates import Email

from typing import Protocol

class NotificationRecipient(Protocol):
    name: str
    email: str

class AbstractNotifications(abc.ABC):

    @staticmethod
    @abc.abstractmethod
    async def send(
            recipients: List[NotificationRecipient],
            message: Email
    ):
        raise NotImplementedError

    @staticmethod
    @abc.abstractmethod
    async def send_to_unregistered(recipients: List[str], message: Email):
        raise NotImplementedError
