import bcrypt
from itsdangerous import URLSafeTimedSerializer

from src.breedgraph import config
from src.breedgraph.domain.commands.accounts import (
    AddAccount,
    UpdateUser,
    Login,
    VerifyEmail,
    AddEmail, RemoveEmail,
    RequestAffiliation, ApproveAffiliation, RemoveAffiliation
)
from src.breedgraph.domain.model.organisations import Access
from src.breedgraph.domain.model.authentication import Token
from src.breedgraph.custom_exceptions import UnauthorisedOperationError

from src.breedgraph.entrypoints.fastapi.graphql.decorators import graphql_payload
from src.breedgraph.entrypoints.fastapi.graphql.resolvers.mutations import graphql_mutation

import logging
logger = logging.getLogger(__name__)

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
    logger.debug(f"Add account: {name}")
    password_hash = bcrypt.hashpw(password.encode(), bcrypt.gensalt()).decode()
    cmd = AddAccount(
        name=name,
        fullname=fullname,
        password_hash=password_hash,
        email=email
    )
    await info.context['bus'].handle(cmd)
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
    async with info.context['bus'].uow.get_repositories() as uow:
        account = await uow.accounts.get(name=username)
        if not account:
            raise UnauthorisedOperationError(fail_message)

        if bcrypt.checkpw(password.encode(), account.user.password_hash.encode()):

            if not account.user.email_verified:
                raise UnauthorisedOperationError("Please confirm email before logging in")

            await info.context['bus'].handle(Login(user=account.user.id))
            token = URLSafeTimedSerializer(config.SECRET_KEY).dumps(
                account.user.id,
                salt=config.LOGIN_SALT
            )
            return Token(access_token=token, token_type="bearer")

        else:
            raise UnauthorisedOperationError(fail_message)

@graphql_mutation.field("edit_user")
@graphql_payload
async def edit_user(
        _,
        info,
        name: str|None = None,
        fullname: str|None = None,
        email: str|None = None,
        password: str|None = None
) -> bool:
    user_id = info.context.get('user_id')
    if user_id is None:
        raise UnauthorisedOperationError("Please provide a valid token")

    logger.debug(f"Edit user: {user_id}")
    if password is not None:
        password_hash = bcrypt.hashpw(password.encode(), bcrypt.gensalt()).decode()
    else:
        password_hash = password
    cmd = UpdateUser(
        user=user_id,
        name=name,
        fullname=fullname,
        password_hash=password_hash,
        email=email
    )
    await info.context['bus'].handle(cmd)
    return True

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

@graphql_mutation.field("add_email")
@graphql_payload
async def add_email(_, info, email: str) -> bool:
    user_id = info.context.get('user_id')
    if user_id is None:
        raise UnauthorisedOperationError("Please provide a valid token")

    logger.debug(f"Add email ({email}) to allowed emails for user {user_id}")
    await info.context['bus'].handle(AddEmail(user=user_id, email=email))
    return True

@graphql_mutation.field("remove_email")
@graphql_payload
async def remove_email(_, info, email: str) -> bool:
    user_id = info.context.get('user_id')
    if user_id is None:
        raise UnauthorisedOperationError("Please provide a valid token")

    logger.debug(f"Remove email ({email}) from allowed emails for user {user_id}")
    await info.context['bus'].handle(RemoveEmail(user=user_id, email=email))
    return True

@graphql_mutation.field("request_affiliation")
@graphql_payload
async def request_affiliation(
        _,
        info,
        team: int,
        access: Access
) -> bool:
    user_id = info.context.get('user_id')
    if user_id is None:
        raise UnauthorisedOperationError("Please provide a valid token")

    logger.debug(f"User {user_id} requests read access from team: {team}")
    cmd = RequestAffiliation(
        user=user_id,
        team=team,
        access=access
    )
    await info.context['bus'].handle(cmd)
    return True

@graphql_mutation.field("approve_affiliation")
@graphql_payload
async def approve_affiliation(
        _,
        info,
        user: int,
        team: int,
        access: Access,
        heritable: bool = False
) -> bool:
    admin_id = info.context.get('admin_id')
    if admin_id is None:
        raise UnauthorisedOperationError("Please provide a valid token")

    logger.debug(f"Admin {admin_id} approving read access to team {team} for user {user}")
    cmd = ApproveAffiliation(
        admin=admin_id,
        user=user,
        team=team,
        access=access,
        heritable=heritable
    )
    await info.context['bus'].handle(cmd)
    return True

@graphql_mutation.field("remove_affiliation")
@graphql_payload
async def remove_affiliation(
        _,
        info,
        user: int,
        team: int,
        access: Access
) -> bool:
    admin_id = info.context.get('user_id')
    if admin_id is None:
        raise UnauthorisedOperationError("Please provide a valid token")

    logger.debug(f"Admin {admin_id} removing read access to team: {team} for user {user}")
    cmd = RemoveAffiliation(
        admin=admin_id,
        user=user,
        team=team,
        access=access
    )
    await info.context['bus'].handle(cmd)
    return True
