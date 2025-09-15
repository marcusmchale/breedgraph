import abc
from typing import List

from src.breedgraph.domain.services.email_templates import Email
from src.breedgraph.domain.model.accounts import UserBase


class AbstractNotifications(abc.ABC):

    @staticmethod
    @abc.abstractmethod
    async def send(
            recipients: List[UserBase],
            message: Email
    ):
        raise NotImplementedError

    @staticmethod
    @abc.abstractmethod
    async def send_to_unregistered(recipients: List[str], message: Email):
        raise NotImplementedError
