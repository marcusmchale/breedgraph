from itsdangerous import URLSafeTimedSerializer
from src.dbtools import config

from src.dbtools.views.accounts import teams
from src.dbtools.domain import events
from src.dbtools.custom_exceptions import (
    NoResultFoundError
)

from src.dbtools.adapters.notifications import emails

from typing import TYPE_CHECKING
if TYPE_CHECKING:
    from src.dbtools.adapters.notifications.notifications import EmailNotifications, AbstractNotifications
    from src.dbtools.adapters.redis.read_model import ReadModel
    from src.dbtools.service_layer.unit_of_work import AbstractUnitOfWork


async def email_user_allowed(
        event: events.accounts.EmailAdded,
        notifications: "EmailNotifications"
):
    # send allowed user a simple email with link to registration address
    await notifications.send_to_unregistered(
        [event.email],
        emails.EmailAddedMessage()
    )


async def add_email_to_read_model(
        event: events.accounts.EmailAdded,
        read_model: "ReadModel"
):
    # send allowed user a simple email with link to registration address
    await read_model.add_email(event.email)


async def remove_email_from_read_model(
        event: events.accounts.EmailRemoved,
        read_model: "ReadModel"
):
    # send allowed user a simple email with link to registration address
    await read_model.remove_email(event.email)


async def send_user_confirm_url(
        event: events.accounts.AccountAdded,
        uow: "AbstractUnitOfWork",
        notifications: "AbstractNotifications"
):
    with uow:
        account = await uow.accounts.get(event.user_id)
        if not account:
            raise NoResultFoundError
        token = URLSafeTimedSerializer(config.SECRET_KEY).dumps(
            account.user.name_lower,
            salt=config.CONFIRM_TOKEN_SALT
        )
        message = emails.UserConfirmMessage(
            account.user,
            token=token
        )
        await notifications.send(
            [account.user],
            message
        )


async def send_confirmed_notification(
        event: events.accounts.AffiliationConfirmed,
        uow: "AbstractUnitOfWork",
        notifications: "AbstractNotifications"
):
    with uow:
        account = await uow.accounts.get(event.user_id)
        if not account:
            raise NoResultFoundError
        team = account.affiliations.get_team(event.team_name)
        message = emails.AffiliationConfirmedMessage(
            account.user,
            team
        )
        await notifications.send(
            [account.user],
            message
        )


async def send_admin_notification(
        event: events.accounts.AdminGranted,
        uow: "AbstractUnitOfWork",
        notifications: "AbstractNotifications"
):
    with uow:
        account = await uow.accounts.get(event.user_id)
        if not account:
            raise NoResultFoundError
        team = account.affiliations.get_team(event.team_name)
        message = emails.AdminGrantedMessage(
            account.user,
            team
        )
        await notifications.send(
            [account.user],
            message
        )
