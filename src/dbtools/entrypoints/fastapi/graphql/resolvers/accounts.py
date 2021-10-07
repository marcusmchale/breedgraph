from fastapi import BackgroundTasks
from src.dbtools.entrypoints.fastapi import bus
from src.dbtools.views.accounts import allowed_email, teams
from src.dbtools.config import pwd_context
from src.dbtools.entrypoints.fastapi.graphql import graphql_mutation, graphql_query
from src.dbtools.entrypoints.fastapi.graphql.decorators import graphql_payload
from src.dbtools.domain.commands.accounts import AddAccount, Login, ConfirmUser

from typing import TYPE_CHECKING
if TYPE_CHECKING:
    from src.dbtools.domain.model.accounts import AccountStored


@graphql_mutation.field("add_account")
@graphql_payload
async def add_account(
        *_,
        username: str,
        fullname: str,
        email: str,
        password: str,
        team_name: str,
        team_fullname: str
):
    password_hash = pwd_context.hash(password)
    cmd = AddAccount(
        username=username,
        fullname=fullname,
        password_hash=password_hash,
        email=email,
        team_name=team_name,
        team_fullname=team_fullname
    )
    await bus.handle(cmd)
    async with bus.uow as uow:
        return await uow.accounts.get(username)


@graphql_mutation.field("login")
@graphql_payload
async def login(
        *_,
        username: str,
        password: str,
        background_tasks: BackgroundTasks
):
    async with bus.uow as uow:
        account = await uow.accounts.get(username)
        if pwd_context.verify(password, account.user.password_hash):
            cmd = Login(
                username=username
            )
            background_tasks.add_task(bus.handle, cmd)
        #todo logic to create and return JWT


@graphql_mutation.field("confirm_user_email")
@graphql_payload
async def confirm_user_email(
        *_,
        token: str
):
    await bus.handle(ConfirmUser(token=token))
    return True


@graphql_query.field("get_teams")
@graphql_payload
async def get_teams(*_):
    async with bus.uow as uow:
        return [team async for team in teams(uow)]


@graphql_query.field("allowed_email")
@graphql_payload
async def allowed_email(*_, email: str = ''):
    if not email:
        return False
    async with bus.uow as uow:
        return True if allowed_email(email, uow) else False


@graphql_query.field("get_account")
@graphql_payload
async def get_account(_, info, username: str = ''):
    async with bus.uow as uow:
        current_account: AccountStored = await uow.accounts.get(username=info.context["name"])
        requested_account: AccountStored = await uow.accounts.get(username=username)
        if current_account == requested_account:
            return requested_account
