from itsdangerous import URLSafeTimedSerializer, SignatureExpired

from src.breedgraph import config
from src.breedgraph.service_layer import unit_of_work
from src.breedgraph.domain import commands, events
from src.breedgraph.domain.model.accounts import (
    UserInput, UserStored,
    Authorisation, Access,
    Affiliation,
    AccountInput, AccountStored
)
from src.breedgraph.domain.model.organisations import (
    TeamInput, TeamStored, Organisation
)
from src.breedgraph.custom_exceptions import (
    NoResultFoundError,
    IdentityExistsError,
    UnauthorisedOperationError
)

import logging


logger = logging.getLogger(__name__)

async def add_first_account(
        cmd: commands.accounts.AddFirstAccount,
        uow: unit_of_work.AbstractUnitOfWork
):
    async with uow.get_repositories() as uow:
        async for _ in uow.accounts.get_all():
            raise UnauthorisedOperationError("This operation is only permitted when no accounts have been registered")
        user = UserInput(
            name=cmd.name,
            fullname=cmd.fullname if cmd.fullname else cmd.name,
            email=cmd.email,
            password_hash=cmd.password_hash
        )

        team = TeamInput(
            name=cmd.team_name,
            fullname=cmd.team_fullname if cmd.team_fullname else cmd.team_name
        )

        organisation: Organisation = await uow.organisations.create(team)

        account: AccountInput = AccountInput(user=user)
        account: AccountStored = await uow.accounts.create(account)

        account.affiliations.append(Affiliation(
                team=organisation.root.id,
                access=Access.ADMIN,
                authorisation = Authorisation.AUTHORISED,
                heritable=True
            )
        )
        await uow.commit()

async def add_account(
        cmd: commands.accounts.AddAccount,
        uow: unit_of_work.AbstractUnitOfWork
):
    async with uow.get_repositories() as uow:
        # Registration email must be included in the allowed emails of some other account
        # todo consider using a view for this, simply all allowed emails (private view)
        async for account in uow.accounts.get_all(
                access_types=[Access.ADMIN],
                authorisations=[Authorisation.AUTHORISED]
        ):
            account: AccountStored
            if cmd.email.casefold() in [i.casefold() for i in account.allowed_emails]:
                break
        else:
            raise UnauthorisedOperationError("Email is not allowed")

        # Check for accounts with same email but not verified
        existing_email: AccountStored = await uow.accounts.get(email=cmd.email)

        if existing_email is not None:
            if not existing_email.user.email_verified:
                await uow.accounts.remove(existing_email)
            else:
                raise UnauthorisedOperationError("This email address is already registered and verified")

        # Check for accounts And whether the name is already taken
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
        cmd: commands.accounts.EditUser,
        uow: unit_of_work.AbstractUnitOfWork
):
    async with uow.get_repositories as uow:
        account = await uow.accounts.get(user_id=cmd.user)
        if cmd.name is not None:
            account.user.name = cmd.name
        if cmd.fullname is not None:
            account.user.fullname = cmd.fullname
        if cmd.email is not None:
            account.user.email = cmd.email
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
            user_id = ts.loads(cmd.token, salt=config.VERIFY_TOKEN_SALT, max_age=config.TOKEN_EXPIRES_MINUTES * 60)
        except SignatureExpired as e:
            logger.debug(f"Attempt to use expired token, signed: {e.date_signed}")
            raise UnauthorisedOperationError("This token has expired")

        account = await uow.accounts.get(user_id=user_id)
        if account is None:
            raise NoResultFoundError

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
    async with uow.get_repositories() as uow:
        account: AccountStored = await uow.accounts.get(user_id=cmd.user)
        account.request_affiliation(cmd.team, Access[cmd.access])
        await uow.commit()

async def approve_affiliation(
        cmd: commands.accounts.ApproveAffiliation,
        uow: unit_of_work.AbstractUnitOfWork
):
    async with uow.get_repositories() as uow:
        account = await uow.accounts.get(user_id=cmd.user)
        organisation = await uow.organisations.get(team_id=cmd.team)
        team = organisation.get_team(team_id=cmd.team)
        if not cmd.admin in team.admins:
            raise UnauthorisedOperationError("Only admins for the given team can perform this operation")

        account.approve_affiliation(cmd.team, Access[cmd.access], cmd.heritable)
        await uow.commit()

async def remove_affiliation(
        cmd: commands.accounts.RemoveAffiliation,
        uow: unit_of_work.AbstractUnitOfWork
):
    async with uow.get_repositories as uow:
        organisation = await uow.organisations.get(team_id=cmd.team)
        team = organisation.teams[cmd.team]
        if not cmd.admin in team.admins:
            raise UnauthorisedOperationError("Only an admins for the given team can perform this operation")
        account = await uow.accounts.get(user_id=cmd.user)
        for a in account.affiliations:
            if all([
                a.team == cmd.team,
                a.access == cmd.access
            ]):
                account.affiliations.remove(a)
                break
        await uow.commit()
