from itsdangerous import URLSafeTimedSerializer, SignatureExpired

from src.breedgraph import config
from src.breedgraph.service_layer import unit_of_work
from src.breedgraph.domain import commands, events
from src.breedgraph.domain.model.accounts import (
    UserInput, UserStored,
    Affiliation, Authorisation, Access,
    AccountInput, AccountStored,
    TeamInput, TeamStored
)
from src.breedgraph.custom_exceptions import (
    NoResultFoundError,
    IdentityExistsError,
    ProtectedNodeError,
    UnauthorisedOperationError
)

import logging


logger = logging.getLogger(__name__)

async def add_first_account(
        cmd: commands.accounts.AddFirstAccount,
        uow: unit_of_work.AbstractUnitOfWork
):
    async with uow:
        async for _ in uow.accounts.get_all():
            raise UnauthorisedOperationError("This operation is only permitted when no accounts have been registered")

        user = UserInput(
            name=cmd.name,
            fullname=cmd.fullname if cmd.fullname else cmd.name,
            email=cmd.email,
            password_hash=cmd.password_hash
        )
        account: AccountInput = AccountInput(user=user)
        account: AccountStored = await uow.accounts.create(account)
        account.affiliations.append(
            Affiliation(
                access = Access.ADMIN,
                authorisation = Authorisation.AUTHORISED,
                team = TeamInput(
                    name=cmd.team_name,
                    fullname=cmd.team_fullname if cmd.team_fullname else cmd.team_name
                )
            )
        )
        account.events.append(events.accounts.AccountAdded(user_id=account.user.id))
        await uow.commit()

async def add_account(
        cmd: commands.accounts.AddAccount,
        uow: unit_of_work.AbstractUnitOfWork
):
    async with uow:

        # Registration email must be included in the allowed emails of some other account
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
        existing_email: AccountStored = await uow.accounts.get_by_email(cmd.email)

        if existing_email is not None:
            if not existing_email.user.email_verified:
                await uow.accounts.remove(existing_email)
            else:
                raise UnauthorisedOperationError("This email address is already registered and verified")

        # Check for accounts And whether the name is already taken
        existing_name: AccountStored = await uow.accounts.get_by_name(cmd.name)
        if existing_name is not None:
            raise IdentityExistsError(f"Username already taken")

        user = UserInput(
            name=cmd.name,
            fullname=cmd.fullname if cmd.fullname else cmd.name,
            email=cmd.email,
            password_hash=cmd.password_hash
        )

        account: AccountInput = AccountInput(user=user)
        account: AccountStored = await uow.accounts.create(account)

        account.events.append(events.accounts.AccountAdded(user_id=account.user.id))
        await uow.commit()

async def verify_email(
        cmd: commands.accounts.VerifyEmail,
        uow: unit_of_work.AbstractUnitOfWork
):
    async with uow:
        ts = URLSafeTimedSerializer(config.SECRET_KEY)

        try:
            user_id = ts.loads(cmd.token, salt=config.VERIFY_TOKEN_SALT, max_age=config.TOKEN_EXPIRES_MINUTES * 60)
        except SignatureExpired as e:
            logger.debug(f"Attempt to use expired token, signed: {e.date_signed}")
            raise UnauthorisedOperationError("This token has expired")

        account = await uow.accounts.get(user_id)
        if account is None:
            raise NoResultFoundError

        account.user.email_verified = True

        # now remove allowed emails - todo, the repository is inefficient for this, consider other implementations
        # maybe a get_by_allowed_emails helper in repository?
        # or handle as an event after the fact.
        async for admin in uow.accounts.get_all(access_types=[Access.ADMIN]):
            for e in admin.allowed_emails:
                if e.casefold() == account.user.email.casefold():
                    admin.allowed_emails.remove(e)

        account.events.append(events.accounts.EmailVerified(user_id=account.user.id))
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
    async with uow:
        if await uow.accounts.get_by_email(cmd.email):
            raise IdentityExistsError("This email is already registered to an account")

        account = await uow.accounts.get(cmd.user_id)

        account.allowed_emails.append(cmd.email)
        account.events.append(events.accounts.EmailAdded(email=cmd.email))
        await uow.commit()

async def remove_email(
        cmd: commands.accounts.RemoveEmail,
        uow: unit_of_work.AbstractUnitOfWork
):
    async with uow:
        account = await uow.accounts.get(cmd.user_id)
        try:
            account.allowed_emails.remove(cmd.email)
        except ValueError:
            raise NoResultFoundError("Email not found among those allowed by this account")
        account.events.append(events.accounts.EmailRemoved(email=cmd.email))
        await uow.commit()


async def add_team(
        cmd: commands.accounts.AddTeam,
        uow: unit_of_work.AbstractUnitOfWork
):
    async with uow:
        account = await uow.accounts.get(cmd.user_id)

        if cmd.parent_id is None:
            for a in account.affiliations:
                if a.access == Access.ADMIN and a.authorisation == Authorisation.AUTHORISED:
                   break
            else:
                raise UnauthorisedOperationError("Only admins can add orphan teams")
        else:
            for a in account.affiliations:
                if not isinstance(a.team, TeamStored):
                    raise(ValueError("Ensure affiliations are stored before adding new teams"))

                if all([
                    a.access == Access.ADMIN,
                    a.authorisation == Authorisation.AUTHORISED,
                    a.team.id == cmd.parent_id
                ]):
                   break
            else:
                raise UnauthorisedOperationError("Only admins for the given parent team can add a child team")

        team = TeamInput(
            name = cmd.name,
            fullname = cmd.fullname if cmd.fullname else cmd.name,
            parent_id = cmd.parent_id
        )

        # Make sure the name/parent combination isn't already found
        for a in account.affiliations:
            if a.team.name.casefold() == team.name.casefold() and a.team.parent_id == team.parent_id:
                raise IdentityExistsError("This team name/parent combination is already found")

        # If you add a team you become its admin (all teams must have at least one admin)
        account.affiliations.append(Affiliation(access=Access.ADMIN, authorisation=Authorisation.AUTHORISED, team=team))
        await uow.commit()

async def request_read(
        cmd: commands.accounts.RequestRead,
        uow: unit_of_work.AbstractUnitOfWork
):
    async with uow:
        account = await uow.accounts.get(cmd.user_id)
        admins = uow.accounts.get_all(teams=[cmd.team_id], access_types=[Access.ADMIN])
        team = None
        async for account in admins:
            for t in account.admins_for:
                if t.id == cmd.team_id:
                    team = t
                    break
            break

        if team is None:
            raise ValueError("No team found")

        #account.read_requests.
        #account.events.append(events.accounts.ReadRequested(cmd.user_id, cmd.team_id))

#async def add_admins(
#        cmd: commands.accounts.AddAdmin,
#        uow: unit_of_work.AbstractUnitOfWork
#):
#    async with uow:
#        auth_account = await uow.accounts.get(cmd.auth_user_id)
#        target_account = await uow.accounts.get(cmd.target_user_id)
#        if not cmd.team_id in auth_account.admins_for:
#            raise UnauthorisedOperationError(
#                f"Authorising user ({auth_account.user.id}) is not an admin for this team {cmd.team_id}."
#            )
#        target_account.admins_for[cmd.team_id] = auth_account.admins_for[cmd.team_id]
#        await uow.commit()
