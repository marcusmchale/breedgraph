from itsdangerous import URLSafeTimedSerializer

from src.breedgraph import config

from src.breedgraph import views
from src.breedgraph.config import pwd_context
from src.breedgraph.entrypoints.fastapi.graphql.decorators import graphql_payload
from src.breedgraph.domain.commands.accounts import (
    AddFirstAccount,
    AddAccount,
    Login,
    VerifyEmail,
    AddTeam,
    AddEmail, RemoveEmail
)

from . import graphql_query, graphql_mutation

from typing import List, Optional
from src.breedgraph.domain.model.accounts import (
    AccountStored, UserOutput, TeamStored, TeamOutput
)
from src.breedgraph.domain.model.authentication import Token

from src.breedgraph.custom_exceptions import (
    NoResultFoundError,
    IdentityExistsError,
    ProtectedNodeError,
    UnauthorisedOperationError
)

import logging
logger = logging.getLogger(__name__)

# todo modify this field so it is only available
#  based on an envar so can disable it after setup
@graphql_mutation.field("add_first_account")
@graphql_payload
async def add_first_account(
        _,
        info,
        name: str,
        fullname: str,
        email: str,
        password: str,
        team_name: str,
        team_fullname: Optional[str] = None
) -> bool:
    password_hash = pwd_context.hash(password)
    cmd = AddFirstAccount(
        name=name,
        fullname=fullname,
        password_hash=password_hash,
        email=email,
        team_name=team_name,
        team_fullname=team_fullname
    )
    await info.context['bus'].handle(cmd)
    return True
    #async with info.context['bus'].uow as uow:
    #    account: AccountStored = await uow.accounts.get_by_name(name)
    #    return [account]

@graphql_mutation.field("add_account")
@graphql_payload
async def add_account(
        _,
        info,
        name: str,
        fullname: str,
        email: str,
        password: str
) -> bool:
    logger.debug(f"Resolver add account: {name}")
    password_hash = pwd_context.hash(password)
    cmd = AddAccount(
        name=name,
        fullname=fullname,
        password_hash=password_hash,
        email=email
    )
    await info.context['bus'].handle(cmd)
    return True
    #async with info.context['bus'].uow as uow:
    #    account: AccountStored = await uow.accounts.get_by_name(name)
    #    return [account]

# the below also has a dedicated endpoint for REST so can follow a simple link
@graphql_mutation.field("verify_email")
@graphql_payload
async def verify_email(
        _,
        info,
        token: str
) -> bool:
    logger.debug(f"Verify email")
    await info.context['bus'].handle(VerifyEmail(token=token))
    return True


@graphql_mutation.field("login")
@graphql_payload
async def login(
        _,
        info,
        username: str,
        password: str
) -> Token:
    logger.debug(f"Log in: {username}")
    fail_message = "Invalid username or password"
    async with info.context['bus'].uow as uow:
        account = await uow.accounts.get_by_name(username)
        if not account:
            raise UnauthorisedOperationError(fail_message)

        if pwd_context.verify(password, account.user.password_hash):

            if not account.user.email_verified:
                raise UnauthorisedOperationError("Please confirm email before logging in")

            await info.context['bus'].handle(Login(user_id=account.user.id))
            token = URLSafeTimedSerializer(config.SECRET_KEY).dumps(
                account.user.id,
                salt=config.LOGIN_SALT
            )
            return Token(access_token=token, token_type="bearer")

        else:
            raise UnauthorisedOperationError(fail_message)

@graphql_mutation.field("add_email")
@graphql_payload
async def add_email(_, info, email: str) -> bool:
    account = info.context.get('account')
    if account is None:
        raise UnauthorisedOperationError("Please provide a valid token")

    logger.debug(f"Add email ({email}) to allowed emails for user {account.user}")
    await info.context['bus'].handle(AddEmail(user_id=account.user.id, email=email))
    return True

@graphql_mutation.field("remove_email")
@graphql_payload
async def remove_email(_, info, email: str) -> bool:
    account = info.context.get('account')
    if account is None:
        raise UnauthorisedOperationError("Please provide a valid token")

    logger.debug(f"Remove email ({email}) from allowed emails for user {account.user}")
    await info.context['bus'].handle(RemoveEmail(user_id=account.user.id, email=email))
    return True

@graphql_mutation.field("add_team")
@graphql_payload
async def add_team(
        _,
        info,
        name: str,
        fullname: Optional[str] = None,
        parent_id: Optional[int] = None
) -> List[TeamOutput]:
    account = info.context.get('account')
    if account is None:
        raise UnauthorisedOperationError("Please provide a valid token")

    logger.debug(f"Add team: {name}")
    cmd = AddTeam(
        user_id=account.user.id,
        name=name,
        fullname=fullname,
        parent_id=parent_id
    )
    await info.context['bus'].handle(cmd)
    return [
        TeamOutput(name=team.name, fullname=team.fullname, id=team.id)
        async for team in views.accounts.teams(info.context['bus'].uow, team_name=name, parent_id=parent_id)
    ]

@graphql_query.field("get_teams")
@graphql_payload
async def get_teams(_, info) -> List[TeamOutput]:
    account = info.context.get('account')
    if account is None:
        raise UnauthorisedOperationError("Please provide a valid token")

    return [
        TeamOutput(name=team.name, fullname=team.fullname, id=team.id)
        async for team in views.accounts.teams(info.context['bus'].uow, user_id=account.user.id)
    ]
