from itsdangerous import URLSafeTimedSerializer
from src.dbtools import config
from src.dbtools.service_layer import unit_of_work
from src.dbtools.domain import commands, events
from src.dbtools.domain.model.accounts import (
    UserInput, UserStored,
    Affiliation, AffiliationLevel, Affiliations,
    AccountInput, AccountStored,
    TeamInput
)
from src.dbtools.custom_exceptions import (
    NoResultFoundError,
    IdentityExistsError,
    ProtectedNodeError,
    UnauthorisedOperationError
)
import logging


logger = logging.getLogger(__name__)


async def add_account(
        cmd: commands.accounts.AddAccount,
        uow: unit_of_work.AbstractUnitOfWork
):
    async with uow:
        existing_accounts = False
        allowed_email = False
        team = None
        async for account in uow.accounts.get_accounts():
            existing_accounts = True
            if account.user.email == cmd.email:
                if not account.user.email_verified:
                    logger.info("Removing unverified account")
                    await uow.accounts.remove(account)
                    continue
                else:
                    logger.warning("Existing account with this verified email address")
            if account.user.name_lower == cmd.username.casefold():
                raise IdentityExistsError(f"Username already taken")
            if cmd.email in account.user.allowed_emails:
                allowed_email = True
                if account.affiliations.primary_team.name_lower == cmd.team_name.casefold():
                    team = account.affiliations.primary_team
                    level = AffiliationLevel(1)
            if not team and cmd.team_name in account.affiliations:
                team = account.affiliations.get_team(cmd.team_name)
                level = AffiliationLevel(0)
        if existing_accounts:
            if not allowed_email:  # unless first user then must be invited by having email added by another user
                raise UnauthorisedOperationError("email not allowed")
            if not level:  # new key
                level = AffiliationLevel(2)
        else:
            level = AffiliationLevel(3)  # first user is set as global admin
        if not team:
            team = TeamInput(cmd.team_name, cmd.team_fullname)
        user = UserInput(
            username=cmd.username,
            fullname=cmd.fullname,
            email=cmd.email,
            password_hash=cmd.password_hash
        )
        affiliation = Affiliation(team=team, level=level, primary=True)
        account = AccountInput(
            user=user,
            affiliations=Affiliations(affiliation)
        )
        account = await uow.accounts.create(account)
        account.events.append(events.accounts.AccountAdded(user_id=account.user.id))
        await uow.commit()


async def login(
        cmd: commands.accounts.Login,
        uow: unit_of_work.AbstractUnitOfWork
):
    # todo logic to record login events etc.
    pass


async def add_email(
        cmd: commands.accounts.AddEmail,
        uow: unit_of_work.AbstractUnitOfWork
):
    async with uow:
        account = await uow.accounts.get(cmd.user_id)
        if not account.affiliations.max_level >= AffiliationLevel.ADMIN:
            raise UnauthorisedOperationError
        account.user.allowed_emails.add(cmd.email)
        account.events.append(events.accounts.EmailAdded(email=cmd.email))
        await uow.commit()


async def remove_email(
        cmd: commands.accounts.RemoveEmail,
        uow: unit_of_work.AbstractUnitOfWork
):
    async with uow:
        account = await uow.accounts.get(cmd.user_id)
        if not account.affiliations.max_level >= AffiliationLevel.ADMIN:
            raise UnauthorisedOperationError
        account.user.allowed_emails.remove(cmd.email)
        account.events.append(events.accounts.EmailRemoved(email=cmd.email))
        await uow.commit()


async def confirm_user_email(
        cmd: commands.accounts.ConfirmUser,
        uow: unit_of_work.AbstractUnitOfWork
):
    async with uow:
        ts = URLSafeTimedSerializer(config.SECRET_KEY)
        user_name_lower = ts.loads(cmd.token, salt=config.CONFIRM_TOKEN_SALT, max_age=86400)
        account = await uow.accounts.get(user_name_lower)
        if not account:
            raise NoResultFoundError
        account.user.email_confirmed = True
        await uow.commit()


async def set_affiliation(
        cmd: commands.accounts.SetAffiliation,
        uow: unit_of_work.AbstractUnitOfWork
):
    async with uow:
        account = await uow.accounts.get(cmd.user_id)
        team = TeamInput(cmd.team_name, cmd.team_fullname)
        level = AffiliationLevel(cmd.level)
        account.affiliations[team] = level
        await uow.commit()
