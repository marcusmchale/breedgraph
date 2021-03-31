import asyncio
from itsdangerous import URLSafeTimedSerializer
from dbtools import config
from dbtools.adapters.notifications import notifications
from dbtools.service_layer import unit_of_work
from dbtools.domain import events
from dbtools.custom_exceptions import (
    NoResultFoundError
)
from dbtools.adapters.notifications import emails


async def email_user_allowed(
        event: events.accounts.EmailAdded,
        notifications: notifications.EmailNotifications
):
    # send allowed user a simple email with link to registration address
    await notifications.send_to_unregistered(
        [event.email],
        emails.EmailAddedMessage()
    )


async def send_user_confirm_url(
        event: events.accounts.AccountAdded,
        uow: unit_of_work.AbstractUnitOfWork,
        notifications: notifications.AbstractNotifications
):
    with uow:
        account = await uow.accounts.get(event.username_lower)
        if not account:
            raise NoResultFoundError
        token = URLSafeTimedSerializer(config.SECRET_KEY).dumps(
            account.user.username_lower,
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
        uow: unit_of_work.AbstractUnitOfWork,
        notifications: notifications.AbstractNotifications
):
    with uow:
        account = await uow.accounts.get(event.username_lower)
        team = await uow.teams.get(event.team_name)
        if not account:
            raise NoResultFoundError
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
        uow: unit_of_work.AbstractUnitOfWork,
        notifications: notifications.AbstractNotifications
):
    with uow:
        account = await uow.accounts.get(event.username_lower)
        team = await uow.teams.get(event.team_name)
        if not account:
            raise NoResultFoundError
        message = emails.AdminGrantedMessage(
            account.user,
            team
        )
        await notifications.send(
            [account.user],
            message
        )
