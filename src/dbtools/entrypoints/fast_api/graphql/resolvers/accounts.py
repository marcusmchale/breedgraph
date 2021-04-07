from fastapi import BackgroundTasks
from dbtools.entrypoints.fast_api import bus
from dbtools.config import pwd_context
from dbtools.entrypoints.fast_api.graphql import graphql_mutation, graphql_query
from dbtools.entrypoints.fast_api.graphql.decorators import graphql_payload
from dbtools.domain.commands.accounts import Initialise, Login, AddAccount, ConfirmUser

from typing import TYPE_CHECKING
if TYPE_CHECKING:
    from dbtools.domain.model.accounts import Account


@graphql_payload
@graphql_mutation.field("initialise")
async def initialise(
        *_,
        team_name: str,
        team_fullname: str,
        username: str,
        user_fullname: str,
        password: str,
        email: str
):
    password_hash = pwd_context.hash(password)
    cmd = Initialise(
        team_name=team_name,
        team_fullname=team_fullname,
        username=username,
        user_fullname=user_fullname,
        password_hash=password_hash,
        email=email
    )
    await bus.handle(cmd)
    return True


@graphql_payload
@graphql_mutation.field("login")
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


@graphql_payload
@graphql_mutation.field("add_account")
async def add_account(
        *_,
        username: str,
        fullname: str,
        email: str,
        password: str,
        team_name: str
):
    password_hash = pwd_context.hash(password)
    cmd = AddAccount(
        username=username,
        fullname=fullname,
        password_hash=password_hash,
        email=email,
        team_name=team_name
    )
    await bus.handle(cmd)
    async with bus.uow as uow:
        return await uow.accounts.get(username)



@graphql_payload
@graphql_mutation.field("confirm_user_email")
async def confirm_user_email(
        *_,
        token: str
):
    await bus.handle(ConfirmUser(token=token))
    return True


@graphql_payload
@graphql_query.field("get_teams")
async def get_teams(*_):
    async with bus.uow as uow:
        return [team async for team in uow.teams.get_all()]


@graphql_payload
@graphql_query.field("allowed_email")
async def allowed_email(*_, email: str = ''):
    if not email:
        return False
    async with bus.uow as uow:
        return True if await uow.emails.get(email) else False


@graphql_payload
@graphql_query.field("get_account")
async def get_account(_, info, username: str = ''):
    async with bus.uow as uow:
        current_account: Account = await uow.accounts.get(username=info.context["username"])
        requested_account: Account = await uow.accounts.get(username=username)
        if current_account == requested_account:
            return requested_account
