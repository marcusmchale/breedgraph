from breedgraph.domain import events
from breedgraph.domain.model.controls import Access
from breedgraph.domain.model.team_trees import TeamInput

from ...infrastructure.notifications import email_templates
from breedgraph.service_layer.infrastructure import AbstractNotifications, AbstractUnitOfWorkFactory

from ..registry import handlers

import logging
logger = logging.getLogger(__name__)


@handlers.event_handler()
async def notify_control_transfer_offered(
        event: events.control_transfers.ControlTransferOffered,
        uow_factory: AbstractUnitOfWorkFactory,
        notifications: AbstractNotifications
):
    async with uow_factory.get_uow() as uow:
        team_tree = await uow.repositories.team_trees.get(team_id=event.recipient_team)
        if team_tree is None:
            return
        team = team_tree.get_team(event.recipient_team)
        if team is None or isinstance(team, TeamInput):
            return

        admins = team_tree.get_affiliates(team_id=event.recipient_team, access=Access.ADMIN)
        admin_users = [(await uow.repositories.accounts.get(user_id=admin)).user for admin in admins]
        if not admin_users:
            return

        message = email_templates.ControlTransferOfferedMessage(
            team=team,
            entity_count=event.entity_count
        )
        await notifications.send(admin_users, message)
