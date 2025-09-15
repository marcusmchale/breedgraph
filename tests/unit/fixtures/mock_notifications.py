from src.breedgraph.service_layer.infrastructure.notifications import AbstractNotifications
from src.breedgraph.domain.model.accounts import UserBase
from src.breedgraph.adapters.aiosmtp.notifications import Email

from typing import List

class FakeNotifications(AbstractNotifications):

    @staticmethod
    async def send_to_unregistered(recipients: List[str], message: Email):
        pass

    @staticmethod
    async def send(recipients: List[UserBase], message: Email):
        pass