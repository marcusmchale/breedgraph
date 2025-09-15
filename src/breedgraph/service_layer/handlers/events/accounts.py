from itsdangerous import URLSafeTimedSerializer
from src.breedgraph import config

from src.breedgraph.domain import events
from src.breedgraph.custom_exceptions import (
    NoResultFoundError
)

from src.breedgraph.domain.services import email_templates
from src.breedgraph.domain.model.organisations import Access, Authorisation
from src.breedgraph.domain.model.accounts import UserOutput

from src.breedgraph.service_layer.infrastructure import AbstractNotifications, AbstractUnitOfWork

from ..registry import handlers

import logging
logger = logging.getLogger(__name__)


@handlers.event_handler()
async def email_user_allowed(
        event: events.accounts.EmailAdded,
        notifications: AbstractNotifications
):
    # send allowed user a simple email with link to registration address
    await notifications.send_to_unregistered(
        [event.email],
        email_templates.EmailAddedMessage()
    )

@handlers.event_handler()
async def send_user_verify_url(
        event: events.accounts.AccountCreated,
        uow: AbstractUnitOfWork,
        notifications: AbstractNotifications
):
    async with uow.get_uow() as uow:
        account = await uow.repositories.accounts.get(user_id=event.user)
        if not account:
            raise NoResultFoundError
        token = URLSafeTimedSerializer(config.SECRET_KEY).dumps(
            {'user_id':account.user.id, 'email':account.user.email},
            salt=config.VERIFY_TOKEN_SALT
        )
        message = email_templates.VerifyEmailMessage(
            account.user,
            token=token
        )
        await notifications.send(
            [account.user],
            message
        )

@handlers.event_handler()
async def email_change_requested(
        event: events.accounts.EmailChangeRequested,
        uow: AbstractUnitOfWork,
        notifications: AbstractNotifications
):
    async with uow.get_uow() as uow:
        logger.debug("Request to change email to %s for user %s", event.email, event.user)
        account = await uow.repositories.accounts.get(user_id=event.user)
        if not account:
            raise NoResultFoundError("Request to change email but matching account was not found")
        token = URLSafeTimedSerializer(config.SECRET_KEY).dumps(
            {'user_id':account.user.id, 'email':event.email},
            salt=config.VERIFY_TOKEN_SALT
        )
        message = email_templates.VerifyEmailMessage(
            account.user,
            token=token
        )
        user = account.user.copy()
        user.email = event.email
        # we don't commit this change, it is just to pass it to the email
        await notifications.send(
            [user],
            message
        )

@handlers.event_handler()
async def email_verified(
        event: events.accounts.EmailVerified,
        uow: AbstractUnitOfWork
):
    # now that email is verified we can remove the allowed email to keep things tidy
    async with uow.get_uow() as uow:
        new_account = await uow.repositories.accounts.get(user_id=event.user)
        async for account in uow.repositories.accounts.get_all(allowed_email=new_account.email):
            account.allowed_emails.remove(new_account.email)

@handlers.event_handler()
async def password_change_requested(
        event: events.accounts.PasswordChangeRequested,
        uow: AbstractUnitOfWork,
        notifications: AbstractNotifications
):
    async with uow.get_uow() as uow:
        account = await uow.repositories.accounts.get(email=event.email)
        if not account:
            raise NoResultFoundError("Request to reset password by email but no account found")

        token = URLSafeTimedSerializer(config.SECRET_KEY).dumps(
            account.user.id,
            salt=config.PASSWORD_RESET_SALT
        )
        message = email_templates.ResetPasswordMessage(
            account.user,
            token=token
        )
        await notifications.send(
            [account.user],
            message
        )

@handlers.event_handler()
async def process_affiliation_request(
        event: events.accounts.AffiliationRequested,
        uow: AbstractUnitOfWork,
        notifications: AbstractNotifications
):
    async with uow.get_uow(redacted=False) as uow:
        organisation = await uow.repositories.organisations.get(team_id = event.team)
        team = organisation.get_team(event.team)
        request = team.affiliations.get_by_access(Access(event.access)).get(event.user)
        admins = organisation.get_affiliates(team_id=event.team, access=Access.ADMIN)
        if event.user in admins:
            # Automatically approve if user is an admin, don't need to email
            request.authorisation = Authorisation.AUTHORISED
            await uow.commit()
        else:
            account = await uow.repositories.accounts.get(user_id=event.user)
            user = UserOutput.from_stored(account.user)
            message = email_templates.AffiliationRequestedMessage(
                requesting_user = user,
                team = team,
                access = Access(event.access)
            )
            admin_accounts = [await uow.repositories.accounts.get(user_id=a) for a in admins]
            admin_users = [a.user for a in admin_accounts]
            await notifications.send(
                admin_users,
                message
            )

@handlers.event_handler()
async def notify_user_approved(
        event: events.accounts.AffiliationApproved,
        uow: AbstractUnitOfWork,
        notifications: AbstractNotifications
):
    async with uow.get_uow(redacted=False) as uow:
        organisation = await uow.repositories.organisations.get(team_id = event.team)
        team = organisation.get_team(event.team)
        account = await uow.repositories.accounts.get(user_id=event.user)
        user = UserOutput.from_stored(account.user)
        message = email_templates.AffiliationApprovedMessage(
            user = user,
            team = team,
            access = Access(event.access)
        )
        await notifications.send(
            [account.user],
            message
        )
