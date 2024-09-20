from itsdangerous import URLSafeTimedSerializer
from src.breedgraph import config

from src.breedgraph.domain import events
from src.breedgraph.custom_exceptions import (
    NoResultFoundError
)
from src.breedgraph.service_layer import unit_of_work
from src.breedgraph.adapters.notifications import emails
from src.breedgraph.domain.model.organisations import Access, Authorisation
from src.breedgraph.domain.model.accounts import UserOutput

from typing import TYPE_CHECKING


if TYPE_CHECKING:
    from src.breedgraph.adapters.notifications.notifications import EmailNotifications, AbstractNotifications
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
        uow: unit_of_work.AbstractUnitOfWork,
        notifications: "AbstractNotifications"
):
    async with uow.get_repositories() as uow:
        account = await uow.accounts.get(user_id=event.user)
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

async def process_affiliation_request(
        event: events.accounts.AffiliationRequested,
        uow: unit_of_work.AbstractUnitOfWork,
        notifications: "AbstractNotifications"
):
    async with uow.get_repositories(redacted=False) as uow:
        organisation = await uow.organisations.get(team_id = event.team)
        team = organisation.get_team(event.team)
        request = team.affiliations.get(event.access).get(event.user)
        admins = organisation.get_affiliates(team_id=event.team, access=Access.ADMIN)

        if event.user in admins:
            # Automatically approve if user is an admin, don't need to email
            request.authorisation = Authorisation.AUTHORISED
            await uow.commit()
        else:
            account = await uow.accounts.get(user_id=event.user)
            user = UserOutput(**account.user.model_dump())
            message = emails.AffiliationRequestedMessage(
                requesting_user = user,
                team = team,
                access = Access[event.access]
            )
            admin_accounts = [await uow.accounts.get(user_id=a) for a in admins]
            admin_users = [a.user for a in admin_accounts]
            await notifications.send(
                admin_users,
                message
            )


async def notify_user_approved(
        event: events.accounts.AffiliationApproved,
        uow: unit_of_work.AbstractUnitOfWork,
        notifications: "AbstractNotifications"
):
    async with uow.get_repositories(redacted=False) as uow:
        organisation = await uow.organisations.get(team_id = event.team)
        team = organisation.get_team(event.team)
        account = await uow.accounts.get(user_id=event.user)
        user = UserOutput(**account.user.model_dump())
        message = emails.AffiliationApprovedMessage(
            user = user,
            team = team,
            access = Access[event.access]
        )
        await notifications.send(
            [account.user],
            message
        )
