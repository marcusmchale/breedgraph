from breedgraph.domain import events
from breedgraph.domain.model.controls import Access, ControlledModelLabel
from breedgraph.service_layer.infrastructure import (
    AbstractErasureLog, ErasureLogEntry, AbstractNotifications, AbstractUnitOfWorkFactory
)
from ...infrastructure.notifications import email_templates

from ..registry import handlers

import logging
logger = logging.getLogger(__name__)


@handlers.event_handler()
async def log_person_erasure(
        event: events.people.PersonErased,
        erasure_log: AbstractErasureLog
):
    """Erasures are logged after they are committed, so a logged erasure always happened."""
    try:
        await erasure_log.append(ErasureLogEntry(
            person_id=event.person_id, erased_at=event.erased_at, created_at=event.recorded_at
        ))
    except Exception:
        logger.critical(
            f"Failed to log the erasure of Person {event.person_id}. "
            f"Add it to the erasure log, or it will not be applied again after restoring a backup.",
            exc_info=True
        )
        raise


@handlers.event_handler()
async def notify_person_claim_requested(
        event: events.people.PersonClaimRequested,
        uow_factory: AbstractUnitOfWorkFactory,
        notifications: AbstractNotifications
):
    """Email the admins of the teams controlling the Person, naming the teams, not who asked (email_templates)"""
    async with uow_factory.get_uow() as uow:
        controller = await uow.controls.get_controller(ControlledModelLabel.PERSON, event.person_id)
        if controller is None:
            return
        admin_ids, teams = set(), []
        for team_id in controller.teams:
            team_tree = await uow.repositories.team_trees.get(team_id=team_id)
            if team_tree is not None:
                admin_ids |= team_tree.get_affiliates(team_id, access=Access.ADMIN)
                teams.append(team_tree.get_team(team_id).name)
        admins = [(await uow.repositories.accounts.get(user_id=admin_id)).user for admin_id in sorted(admin_ids)]
    if admins:
        await notifications.send(admins, email_templates.PersonClaimRequestedMessage(teams=sorted(teams)))


@handlers.event_handler()
async def notify_person_linked(
        event: events.people.PersonLinked,
        uow_factory: AbstractUnitOfWorkFactory,
        notifications: AbstractNotifications
):
    async with uow_factory.get_uow() as uow:
        account = await uow.repositories.accounts.get(user_id=event.user_id)
    if account is not None:
        await notifications.send([account.user], email_templates.PersonLinkedMessage(account.user))
