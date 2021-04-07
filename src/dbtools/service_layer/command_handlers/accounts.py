from fastapi import BackgroundTasks
from itsdangerous import URLSafeTimedSerializer
from dbtools import config
from dbtools.service_layer import unit_of_work
from dbtools.domain import commands, events
from dbtools.domain.model.accounts import UserRegistered, Affiliation, AffiliationLevel, Affiliations, Account, Team
from dbtools.custom_exceptions import (
    NoResultFoundError,
    IdentityExistsError,
    ProtectedNodeError,
    UnauthorisedOperationError
)


async def initialise(
        cmd: commands.accounts.Initialise,
        uow: unit_of_work.AbstractUnitOfWork
):
    async with uow:
        if any([team async for team in uow.teams.get_all()]):
            raise IdentityExistsError(
                'Already initialised'
            )
        team = Team(name=cmd.team_name, fullname=cmd.team_fullname)
        user = UserRegistered(
            id=-1,  # replaced with incremented integer when added to repository
            username=cmd.username,
            fullname=cmd.user_fullname,
            email=cmd.email,
            password_hash=cmd.password_hash,
            email_confirmed=True,
        )
        affiliation = Affiliation(team=team, level=AffiliationLevel(3))
        account = Account(
            user=user,
            affiliations=Affiliations(affiliation),
        )
        await uow.teams.add(team)
        await uow.accounts.add(account)
        account.events.append(events.accounts.AccountAdded(username_lower=user.username_lower))
        await uow.commit()


async def login(
        cmd: commands.accounts.Login,
        uow: unit_of_work.AbstractUnitOfWork
):
    # todo logic to record login events etc.
    pass


async def add_team(
        cmd: commands.accounts.AddTeam,
        uow: unit_of_work.AbstractUnitOfWork
):
    async with uow:
        admin = await uow.accounts.get(cmd.admin_username_lower)
        if not admin.affiliations.max_level >= AffiliationLevel.ADMIN:
            raise UnauthorisedOperationError
        team = Team(name=cmd.name, fullname=cmd.fullname)
        if uow.teams.get(team.name):
            raise IdentityExistsError
        await uow.teams.add(team)
        await uow.commit()


async def add_email(
        cmd: commands.accounts.AddEmail,
        uow: unit_of_work.AbstractUnitOfWork
):
    async with uow:
        admin = await uow.accounts.get(cmd.admin_username_lower)
        if not admin.affiliations.max_level >= AffiliationLevel.ADMIN:
            raise UnauthorisedOperationError
        await uow.emails.add(admin.user, cmd.user_email)
        admin.events.append(events.accounts.EmailAdded(email=cmd.user_email))
        await uow.commit()


async def remove_email(
        cmd: commands.accounts.RemoveEmail,
        uow: unit_of_work.AbstractUnitOfWork
):
    async with uow:
        admin = await uow.accounts.get(cmd.admin_username_lower)
        if not admin.affiliations.max_level >= AffiliationLevel.ADMIN:
            raise UnauthorisedOperationError
        await uow.emails.remove(admin.user, cmd.user_email)
        await uow.commit()


async def add_account(
        cmd: commands.accounts.AddAccount,
        uow: unit_of_work.AbstractUnitOfWork
):
    async with uow:
        if not await uow.emails.get(cmd.email):
            raise UnauthorisedOperationError
        account_by_email = await uow.accounts.get_by_email(cmd.email)
        if account_by_email:
            if account_by_email.user.email_confirmed:
                raise ProtectedNodeError
            else:
                await uow.accounts.remove(account_by_email)
        if await uow.accounts.get(cmd.username):
            raise IdentityExistsError
        user = UserRegistered(
            username=cmd.username,
            fullname=cmd.fullname,
            password_hash=cmd.password_hash,
            email=cmd.email
        )
        team = await uow.teams.get(cmd.team_name)
        affiliation = Affiliation(team=team, level=AffiliationLevel(0))
        account = Account(
            user=user,
            affiliations=Affiliations(affiliation)
        )
        await uow.accounts.add(account)
        account.events.append(events.accounts.AccountAdded(username_lower=user.username_lower))
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


async def add_affiliation(
        cmd: commands.accounts.AddAffiliation,
        uow: unit_of_work.AbstractUnitOfWork
):
    async with uow:
        account = await uow.accounts.get(cmd.username_lower)
        team = await uow.teams.get(cmd.team_name)
        affiliation = Affiliation(team=team, level=AffiliationLevel(0))
        account.affiliations.add(affiliation)
        await uow.commit()


async def set_affiliation_level(
        cmd: commands.accounts.SetAffiliationLevel,
        uow: unit_of_work.AbstractUnitOfWork
):
    async with uow:
        account = await uow.accounts.get(cmd.username_lower)
        affiliation = account.affiliations.get_by_team_name(cmd.team_name)
        affiliation.level = AffiliationLevel(cmd.level)
        await uow.commit()
