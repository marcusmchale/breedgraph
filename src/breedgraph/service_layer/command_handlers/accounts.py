from itsdangerous import URLSafeTimedSerializer, SignatureExpired

from src.breedgraph import config
from src.breedgraph.service_layer import unit_of_work
from src.breedgraph.domain import commands, events
from src.breedgraph.domain.model.accounts import (
    UserInput, UserStored,
    AccountInput, AccountStored,
    TeamInput, Email, AffiliationType
)
from src.breedgraph import views
from src.breedgraph.custom_exceptions import (
    NoResultFoundError,
    IdentityExistsError,
    ProtectedNodeError,
    UnauthorisedOperationError
)

import logging


logger = logging.getLogger(__name__)


async def add_user(
        cmd: commands.accounts.AddUser,
        uow: unit_of_work.AbstractUnitOfWork
):
    async with uow:
        # First user gets to create account without needing to be verified
        # Registration email must be included in the allowed emails of some other account
        first_user = True
        email_allowed = False
        email = Email(address=cmd.email)

        async for account in uow.accounts.get_all():
            first_user = False
            if email in account.allowed_emails:
                email_allowed = True
                break

        if first_user:
            logger.warning("First user registration")

        if not(email_allowed or first_user):
            raise UnauthorisedOperationError("Email is not allowed")

        # Check for prior registration
        account_existing_email = await uow.accounts.get_by_email(cmd.email)
        # And whether the username is already taken
        account_existing_username = await uow.accounts.get_by_name(cmd.name)

        if account_existing_email:
            try:
                logger.info("Removing account without verified email")
                await uow.accounts.remove(account_existing_email)
            except ProtectedNodeError:
                logger.warning("Existing account with this verified email address")
                raise ProtectedNodeError(f"Verified account cannot be removed")

        if account_existing_username and not account_existing_username == account_existing_email:
            logger.warning("Existing account with this username")
            raise IdentityExistsError(f"Username already taken")

        user = UserInput(
            name=cmd.name,
            fullname=cmd.fullname,
            email=cmd.email,
            password_hash=cmd.password_hash
        )
        account = AccountInput(
            user=user
        )
        account = await uow.accounts.create(account)
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
        account.events.append(events.accounts.EmailVerified(user_id=account.user.id))
        await uow.commit()

async def login(
        cmd: commands.accounts.Login,
        uow: unit_of_work.AbstractUnitOfWork
):
    # todo logic to record login events etc.
    pass
    # raise NotImplementedError


async def add_team(
        cmd: commands.accounts.AddTeam,
        uow: unit_of_work.AbstractUnitOfWork
):
    async with uow:
        first_team = True
        async for account in uow.accounts.get_all():
            if account.reads_from or account.writes_for or account.admins_for:
                first_team = False
                break

        account = await uow.accounts.get(cmd.user_id)
        # Team creation rules:
        #  - Admins only can add teams but the first team can always be created
        if not first_team and not account.admins_for:
            raise UnauthorisedOperationError("Only admins can create teams")
        #  - Admins can create orphan teams, but can only create children to teams for which they are admin
        if cmd.parent_id is not None and cmd.parent_id not in account.admins_for:
            raise UnauthorisedOperationError("Teams may be created as orphans or as children of teams for which the user is admin")

        team = TeamInput(
            name = cmd.name,
            fullname = cmd.fullname if cmd.fullname else cmd.name,
            parent_id = cmd.parent_id
        )
        account.admins_for.append(team)  # If you add a team you become its admin (all teams must have at least one admin)
        await uow.commit()


async def add_email(
        cmd: commands.accounts.AddEmail,
        uow: unit_of_work.AbstractUnitOfWork
):
    async with uow:
        account = await uow.accounts.get(cmd.user_id)
        account.allowed_emails.append(Email(address=cmd.email))
        account.events.append(events.accounts.EmailAdded(email=cmd.email))
        await uow.commit()


async def remove_email(
        cmd: commands.accounts.RemoveEmail,
        uow: unit_of_work.AbstractUnitOfWork
):
    async with uow:
        account = await uow.accounts.get(cmd.user_id)
        account.user.allowed_emails.remove(Email(address=cmd.email))
        account.events.append(events.accounts.EmailRemoved(email=cmd.email))
        await uow.commit()


async def request_read(
        cmd: commands.accounts.RequestRead,
        uow: unit_of_work.AbstractUnitOfWork
):
    async with uow:
        account = await uow.accounts.get(cmd.user_id)
        admins = uow.accounts.get_by_affiliation([cmd.team_id], [AffiliationType.ADMIN])
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
