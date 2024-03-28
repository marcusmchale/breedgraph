from itsdangerous import URLSafeTimedSerializer
from src.breedgraph import config

from src.breedgraph import views
from src.breedgraph.config import pwd_context
from src.breedgraph.entrypoints.fastapi.graphql.decorators import graphql_payload
from src.breedgraph.domain.commands.accounts import AddUser, Login, VerifyEmail, AddTeam, AddEmail

from . import graphql_query, graphql_mutation

from typing import List, Optional
from src.breedgraph.domain.model.accounts import AccountStored, AccountOutput, UserOutput, TeamStored, TeamOutput
from src.breedgraph.domain.model.authentication import Token

from src.breedgraph.custom_exceptions import (
    NoResultFoundError,
    IdentityExistsError,
    ProtectedNodeError,
    UnauthorisedOperationError
)


import logging
logger = logging.getLogger(__name__)

@graphql_mutation.field("add_user")
@graphql_payload
async def add_user(
        _,
        info,
        name: str,
        fullname: str,
        email: str,
        password: str
) -> [AccountOutput]:
    logger.debug(f"Resolver add user: {name}")
    password_hash = pwd_context.hash(password)
    cmd = AddUser(
        name=name,
        fullname=fullname,
        password_hash=password_hash,
        email=email
    )
    await info.context['bus'].handle(cmd)
    async with info.context['bus'].uow as uow:
        account_stored = await uow.accounts.get_by_name(name)
        user: UserOutput = UserOutput(
            id=account_stored.user.id,
            name=account_stored.user.name,
            fullname=account_stored.user.fullname,
            email=account_stored.user.email,
            email_verified=account_stored.user.email_verified
        )
        return [AccountOutput(user=user)]

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
    async with info.context['bus'].uow as uow:
        account = await uow.accounts.get_by_name(username)
        if account is None:
            raise UnauthorisedOperationError("Please provide a valid token")

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
            raise UnauthorisedOperationError("Invalid login credentials")

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

    logger.debug(f"Resolver add team: {name}")
    cmd = AddTeam(
        user_id=account.user.id,
        name=name,
        fullname=fullname,
        parent_id=parent_id
    )
    await info.context['bus'].handle(cmd)
    async with info.context['bus'].uow as uow:
        team = await views.accounts.team(uow=uow, team_name=name, parent_id = parent_id)
        return [team]

@graphql_mutation.field("add_email")
@graphql_payload
async def add_email(_, info, email: str) -> bool:
    account = info.context.get('account')
    if account is None:
        raise UnauthorisedOperationError("Please provide a valid token")

    logger.debug(f"Add email ({email}) to allowed emails for user {account.user}")
    await info.context['bus'].handle(AddEmail(user_id=account.user.id, email=email))
    return True




@graphql_query.field("get_teams")   #todo this needs to filter by teams that are known to the account
@graphql_payload
async def get_teams(_, info) -> List[TeamOutput]:
    account = info.context.get('account')
    logger.debug(f"Get teams")
    async with info.context['bus'].uow as uow:
        return await views.accounts.teams(uow)





#@graphql_query.field("allowed_email")
#@graphql_payload
#async def allowed_email(_, info, email: str = '') -> bool:
#    logger.debug(f"Check email allowed {email}")
#    if not email:
#        return False
#    async with info.context['bus'].uow as uow:
#        return await views.accounts.allowed_email(email, uow)


#@graphql_query.field("get_account")
#@graphql_payload
#async def get_account(_, info, username: str = '') -> AccountOutput:
#    logger.debug(f"Get account: {username}")
#    async with info.context['bus'].uow as uow:
#        current_account: AccountStored = await uow.accounts.get(username=info.context["name"])
#        requested_account: AccountStored = await uow.accounts.get(username=username)
#        if current_account == requested_account:
#            return requested_account
