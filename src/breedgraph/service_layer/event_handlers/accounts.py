from itsdangerous import URLSafeTimedSerializer
from src.breedgraph import config

#from src.breedgraph.views.accounts import teams
from src.breedgraph.domain import events
from src.breedgraph.custom_exceptions import (
    NoResultFoundError
)

from src.breedgraph.adapters.notifications import emails
from src.breedgraph.domain.model.accounts import Access, Authorisation

from src.breedgraph.domain.model.organisations import (
    TeamStored
)

from typing import TYPE_CHECKING
if TYPE_CHECKING:
    from src.breedgraph.adapters.notifications.notifications import EmailNotifications, AbstractNotifications
    from src.breedgraph.adapters.redis.read_model import ReadModel
    from src.breedgraph.service_layer.unit_of_work import AbstractUnitOfWork


async def email_user_allowed(
        event: events.accounts.EmailAdded,
        notifications: "EmailNotifications"
):
    # send allowed user a simple email with link to registration address
    await notifications.send_to_unregistered(
        [event.email],
        emails.EmailAddedMessage()
    )

async def send_user_verify_url(
        event: events.accounts.AccountAdded,
        uow: "AbstractUnitOfWork",
        notifications: "AbstractNotifications"
):
    async with uow:
        account = await uow.accounts.get(event.user)
        if not account:
            raise NoResultFoundError
        token = URLSafeTimedSerializer(config.SECRET_KEY).dumps(
            account.user.id,
            salt=config.VERIFY_TOKEN_SALT
        )
        message = emails.VerifyEmailMessage(
            account.user,
            token=token
        )
        await notifications.send(
            [account.user],
            message
        )

async def email_verified(
        event: events.accounts.EmailVerified,
        uow: "AbstractUnitOfWork"
):
    pass

async def email_admins_read_request(
        event: events.accounts.ReadRequested,
        uow: "AbstractUnitOfWork",
        notifications: "AbstractNotifications"
):
    async with uow:
        account = await uow.accounts.get(event.user)
        organisation = await uow.organisations.get(event.team)
        team = organisation.get_team(event.team)

        # todo consider implementing a method to fetch a list of ids in the repository
        admins = [await uow.accounts.get(admin_id) for admin_id in team.admins]

        message = emails.ReadRequestedMessage(
            requesting_user = account.user,
            team = team
        )
        await notifications.send(
            [admin.user for admin in admins],
            message
        )


async def email_user_read_added(
        event: events.accounts.ReadRequested,
        uow: "AbstractUnitOfWork",
        notifications: "AbstractNotifications"
):
    async with uow:
        account = await uow.accounts.get(event.user)
        organisation = await uow.organisations.get(event.team)
        team = organisation.get_team(event.team)

        message = emails.ReadAddedMessage(
            user = account.user,
            team = team
        )
        await notifications.send(
            [account.user],
            message
        )


#
#async def add_email_to_read_model(
#        event: events.accounts.EmailAdded,
#        read_model: "ReadModel"
#):
#    # send allowed user a simple email with link to registration address
#    await read_model.add_email(event.email)
#
#
#async def remove_email_from_read_model(
#        event: events.accounts.EmailRemoved,
#        read_model: "ReadModel"
#):
#    # send allowed user a simple email with link to registration address
#    await read_model.remove_email(event.email)
#

#
#async def send_confirmed_notification(
#        event: events.accounts.AffiliationConfirmed,
#        uow: "AbstractUnitOfWork",
#        notifications: "AbstractNotifications"
#):
#    with uow:
#        account = await uow.accounts.get(event.user_id)
#        if not account:
#            raise NoResultFoundError
#        team = account.affiliations.get_team(event.team_name)
#        message = emails.AffiliationConfirmedMessage(
#            account.user,
#            team
#        )
#        await notifications.send(
#            [account.user],
#            message
#        )
#
#
#async def send_admin_notification(
#        event: events.accounts.AdminGranted,
#        uow: "AbstractUnitOfWork",
#        notifications: "AbstractNotifications"
#):
#    with uow:
#        account = await uow.accounts.get(event.user_id)
#        if not account:
#            raise NoResultFoundError
#        team = account.affiliations.get_team(event.team_name)
#        message = emails.AdminGrantedMessage(
#            account.user,
#            team
#        )
#        await notifications.send(
#            [account.user],
#            message
#        )
