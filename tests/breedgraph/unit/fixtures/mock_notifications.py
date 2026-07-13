from breedgraph.service_layer.infrastructure.notifications.notifications import AbstractNotifications, NotificationRecipient
from breedgraph.adapters.aiosmtp.notifications import Email

from typing import List

class FakeNotifications(AbstractNotifications):

    @staticmethod
    async def send_to_unregistered(recipients: List[str], message: Email):
        pass

    @staticmethod
    async def send(recipients: List[NotificationRecipient], message: Email):
        pass