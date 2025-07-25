from itsdangerous import URLSafeTimedSerializer, SignatureExpired

from src.breedgraph import config
from src.breedgraph.service_layer import unit_of_work
from src.breedgraph.domain import commands, events
from src.breedgraph import views

from src.breedgraph.domain.model.accounts import (
    UserInput, UserStored,
    AccountInput, AccountStored
)
from src.breedgraph.domain.model.organisations import (
    TeamInput, TeamStored, Organisation,
    Authorisation, Access,
    Affiliation,
)
from src.breedgraph.custom_exceptions import (
    NoResultFoundError,
    IdentityExistsError,
    UnauthorisedOperationError
)

import logging


logger = logging.getLogger(__name__)

async def add_account(
        cmd: commands.accounts.AddAccount,
        uow: unit_of_work.AbstractUnitOfWork
):
    # First use views to quickly check if any accounts exist
    if await views.accounts.check_any_account(uow):
        # And if the email is included in the allowed emails of some other account
        if not await views.accounts.check_allowed_email(uow, cmd.email):
            raise UnauthorisedOperationError("Please contact an existing user to be invited")

    async with uow.get_repositories() as uow:
        # Check for accounts with same email but not verified
        existing_email: AccountStored = await uow.accounts.get(email=cmd.email)
        if existing_email is not None:
            # and if it exists but isn't verified
            if not existing_email.user.email_verified:
                # then allow removing the old one to replace it with the current registration attempt
                logger.debug("Removing an unverified account to replace it with a new one")
                await uow.accounts.remove(existing_email)
            else:
                # but if it is verified then raise an error
                raise UnauthorisedOperationError("This email address is already registered and verified")

        # Check for accounts with the same username. These should be unique
        existing_name: AccountStored = await uow.accounts.get(name=cmd.name)
        if existing_name is not None:
            raise IdentityExistsError(f"Username already taken")

        user = UserInput(
            name=cmd.name,
            fullname=cmd.fullname if cmd.fullname else cmd.name,
            email=cmd.email,
            password_hash=cmd.password_hash
        )

        account: AccountInput = AccountInput(user=user)
        await uow.accounts.create(account)
        await uow.commit()

async def edit_user(
        cmd: commands.accounts.UpdateUser,
        uow: unit_of_work.AbstractUnitOfWork
):
    async with uow.get_repositories() as uow:
        account = await uow.accounts.get(user_id=cmd.user)
        if cmd.name is not None:
            account.user.name = cmd.name
        if cmd.fullname is not None:
            account.user.fullname = cmd.fullname
        if cmd.email is not None and cmd.email != account.user.email:
            # Don't change the email, but initiate the request event
            account.events.append(events.accounts.EmailChangeRequested(user=account.user.id, email=cmd.email))
        if cmd.password_hash is not None:
            account.user.password_hash = cmd.password_hash
        await uow.commit()


async def verify_email(
        cmd: commands.accounts.VerifyEmail,
        uow: unit_of_work.AbstractUnitOfWork
):
    async with uow.get_repositories() as uow:
        ts = URLSafeTimedSerializer(config.SECRET_KEY)

        try:
            data = ts.loads(cmd.token, salt=config.VERIFY_TOKEN_SALT, max_age=config.VERIFY_EXPIRES * 60)
            user_id = data['user_id']
            email = data['email']

        except SignatureExpired as e:
            logger.debug(f"Attempt to use expired token, signed: {e.date_signed}")
            raise UnauthorisedOperationError("This token has expired")

        account = await uow.accounts.get(user_id=user_id)
        if account is None:
            raise NoResultFoundError

        existing_email: AccountStored = await uow.accounts.get(email=email)
        if existing_email is not None and existing_email.user.email_verified:
            raise IdentityExistsError("This email address is already verified on another account")

        account.user.email = email
        account.verify_email()

        # now remove allowed emails and establish the ALLOWED_REGISTRATION relationship
        # todo this relationship is not currently used but may be useful in auditing DB usage and admin activities
        async for admin in uow.accounts.get_all(access_types=[Access.ADMIN], authorisations=[Authorisation.AUTHORISED]):
            for e in admin.allowed_emails:
                if e.casefold() == account.user.email.casefold():
                    admin.allowed_emails.remove(e)

        await uow.commit()

async def login(
        cmd: commands.accounts.Login,
        uow: unit_of_work.AbstractUnitOfWork
):
    # todo logic to record login events etc.
    pass
    # raise NotImplementedError

async def add_email(
        cmd: commands.accounts.AddEmail,
        uow: unit_of_work.AbstractUnitOfWork
):
    async with uow.get_repositories() as uow:
        if await uow.accounts.get(email=cmd.email):
            raise IdentityExistsError("This email is already registered to an account")

        account:AccountStored = await uow.accounts.get(user_id=cmd.user)
        account.allow_email(cmd.email)
        await uow.commit()

async def remove_email(
        cmd: commands.accounts.RemoveEmail,
        uow: unit_of_work.AbstractUnitOfWork
):
    async with uow.get_repositories() as uow:
        account = await uow.accounts.get(user_id=cmd.user)
        try:
            account.allowed_emails.remove(cmd.email)
        except ValueError:
            raise NoResultFoundError("Email not found among those allowed by this account")
        await uow.commit()

async def request_affiliation(
        cmd: commands.accounts.RequestAffiliation,
        uow: unit_of_work.AbstractUnitOfWork
):
    async with uow.get_repositories(user_id=cmd.user) as uow:
        organisation = await uow.organisations.get(team_id=cmd.team)
        organisation.request_affiliation(
            agent_id=cmd.user,
            user_id=cmd.user,
            team_id=cmd.team,
            access=Access(cmd.access),
            heritable=cmd.heritable
        )
        await uow.commit()

async def approve_affiliation(
        cmd: commands.accounts.ApproveAffiliation,
        uow: unit_of_work.AbstractUnitOfWork
):
    async with uow.get_repositories(user_id=cmd.agent) as uow:
        organisation = await uow.organisations.get(team_id=cmd.team)
        organisation.authorise_affiliation(
            agent_id = cmd.agent,
            team_id = cmd.team,
            user_id = cmd.user,
            access=Access(cmd.access),
            heritable=cmd.heritable
        )
        await uow.commit()

async def remove_affiliation(
        cmd: commands.accounts.RemoveAffiliation,
        uow: unit_of_work.AbstractUnitOfWork
):
    async with uow.get_repositories(user_id=cmd.agent) as uow:
        organisation = await uow.organisations.get(team_id=cmd.team)
        organisation.remove_affiliation(
            agent_id = cmd.agent,
            team_id = cmd.team,
            user_id = cmd.user,
            access=Access(cmd.access)
        )
        await uow.commit()

async def revoke_affiliation(
        cmd: commands.accounts.RevokeAffiliation,
        uow: unit_of_work.AbstractUnitOfWork
):
    async with uow.get_repositories(user_id=cmd.agent) as uow:
        organisation = await uow.organisations.get(team_id=cmd.team)
        organisation.revoke_affiliation(
            agent_id = cmd.agent,
            team_id = cmd.team,
            user_id = cmd.user,
            access=Access(cmd.access)
        )
        await uow.commit()