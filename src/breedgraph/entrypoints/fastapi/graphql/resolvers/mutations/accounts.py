import bcrypt
from itsdangerous import URLSafeTimedSerializer, SignatureExpired

from src.breedgraph import config
from src.breedgraph.domain.commands.accounts import (
    CreateAccount,
    UpdateUser,
    Login,
    VerifyEmail,
    AddEmail, RemoveEmail,
    RequestAffiliation, ApproveAffiliation, RemoveAffiliation, RevokeAffiliation
)
from src.breedgraph.domain.events.accounts import (
    PasswordChangeRequested
)
from src.breedgraph.domain.model.organisations import Access
from src.breedgraph.custom_exceptions import UnauthorisedOperationError

from src.breedgraph.entrypoints.fastapi.graphql.decorators import graphql_payload, require_authentication
from src.breedgraph.entrypoints.fastapi.graphql.resolvers.mutations import graphql_mutation

from src.breedgraph.config import LOGIN_EXPIRES

import logging
logger = logging.getLogger(__name__)

@graphql_mutation.field("create_account")
@graphql_payload
async def create_account(
        _,
        info,
        name: str,
        fullname: str,
        email: str,
        password: str
) -> bool:
    logger.debug(f"Add account: {name}")
    # the bcrypt hash result includes the salt,
    # it is concatenated into the hash then encoded in a modified base64
    # so we can just store the hash in db
    password_hash = bcrypt.hashpw(password.encode(), bcrypt.gensalt()).decode()
    cmd = CreateAccount(
        name=name,
        fullname=fullname,
        password_hash=password_hash,
        email=email
    )
    await info.context['bus'].handle(cmd)
    return True

@graphql_mutation.field("request_password_reset")
@graphql_payload
async def request_change_password(
        _,
        info,
        email: str
) -> bool:
    logger.debug(f"Request change password for email: {email}")
    await info.context['bus'].handle(PasswordChangeRequested(email=email))
    return True

@graphql_mutation.field("reset_password")
@graphql_payload
async def reset_password(
        _,
        info,
        token: str,
        password: str
) -> bool:
    ts = URLSafeTimedSerializer(config.SECRET_KEY)
    try:
        user_id = ts.loads(token, salt=config.PASSWORD_RESET_SALT, max_age=config.PASSWORD_RESET_EXPIRES * 60)
    except SignatureExpired as e:
        logger.debug(f"Attempt to use expired token, signed: {e.date_signed}")
        raise UnauthorisedOperationError("This token has expired")

    async with info.context['bus'].uow.get_repositories() as uow:
        account = await uow.accounts.get(user_id=user_id)
        if not account:
            raise UnauthorisedOperationError("Token not valid because user was not found")
        logger.debug(f"Change password for user: {account.user.id}")
        password_hash = bcrypt.hashpw(password.encode(), bcrypt.gensalt()).decode()

    cmd = UpdateUser(user=user_id, password_hash=password_hash)
    await info.context['bus'].handle(cmd)
    return True

@graphql_mutation.field("login")
@graphql_payload
async def login(
        _,
        info,
        username: str,
        password: str
) -> bool:
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
            token = info.context['auth_service'].create_token(account.user.id)

            # Queue the cookie to be set on the response
            cookie_data = {
                "key": "auth_token",
                "value": token,
                "max_age": LOGIN_EXPIRES * 60,  # Convert minutes to seconds
                "httponly": True,
                "secure": True,  # Set to True for HTTPS
                "samesite": "strict",
                "path": "/"
            }
            info.context["cookies_to_set"].append(cookie_data)

            logger.debug(f"Auth token cookie queued for user {account.user.id}")
            return True
        else:
            raise UnauthorisedOperationError(fail_message)


@graphql_mutation.field("logout")
@graphql_payload
@require_authentication
async def logout(_, info) -> bool:
    user_id = info.context.get('user_id')
    logger.debug(f"Logout user: {user_id}")

    # Queue the cookie to be removed on the response
    cookie_data = {
        "key": "auth_token",
        "value": "",
        "max_age": 0,  # Expire immediately
        "httponly": True,
        "secure": True,
        "samesite": "strict",
        "path": "/"
    }
    info.context["cookies_to_set"].append(cookie_data)

    logger.debug(f"Auth token cookie queued for removal for user {user_id}")
    return True


@graphql_mutation.field("update_user")
@graphql_payload
@require_authentication
async def update_user(
        _,
        info,
        name: str|None = None,
        fullname: str|None = None,
        email: str|None = None,
        password: str|None = None
) -> bool:
    user_id = info.context.get("user_id")
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
@require_authentication
async def add_email(_, info, email: str) -> bool:
    user_id = info.context.get('user_id')
    logger.debug(f"Add email ({email}) to allowed emails for user {user_id}")
    await info.context['bus'].handle(AddEmail(user=user_id, email=email))
    return True

@graphql_mutation.field("remove_email")
@graphql_payload
@require_authentication
async def remove_email(_, info, email: str) -> bool:
    user_id = info.context.get('user_id')

    logger.debug(f"Remove email ({email}) from allowed emails for user {user_id}")
    await info.context['bus'].handle(RemoveEmail(user=user_id, email=email))
    return True

@graphql_mutation.field("request_affiliation")
@graphql_payload
@require_authentication
async def request_affiliation(
        _,
        info,
        team: int,
        access: Access,
        heritable: bool = True
        # most requests should be heritable to allow an admin to authorise to a child team
        # however, since authorisation is automatic for admins,
        # the admin may wish to specify a non heritable affiliation
) -> bool:
    user_id = info.context.get('user_id')
    logger.debug(f"User {user_id} requests {access} for team: {team}")
    cmd = RequestAffiliation(
        user=user_id,
        team=team,
        access=access,
        heritable=heritable
    )
    await info.context['bus'].handle(cmd)
    return True

@graphql_mutation.field("approve_affiliation")
@graphql_payload
@require_authentication
async def approve_affiliation(
        _,
        info,
        user: int,
        team: int,
        access: Access,
        heritable: bool = False
) -> bool:
    agent_id = info.context.get('user_id')
    logger.debug(f"Agent {agent_id} approving {access} to team {team} for user {user}")
    cmd = ApproveAffiliation(
        agent=agent_id,
        user=user,
        team=team,
        access=access,
        heritable=heritable
    )
    await info.context['bus'].handle(cmd)
    return True

@graphql_mutation.field("remove_affiliation")
@graphql_payload
@require_authentication
async def remove_affiliation(
        _,
        info,
        team: int,
        access: Access
) -> bool:
    agent_id = info.context.get('user_id')
    logger.debug(f"Agent {agent_id} removing {access} for team: {team}")
    cmd = RemoveAffiliation(
        agent=agent_id,
        user=agent_id,
        team=team,
        access=access
    )
    await info.context['bus'].handle(cmd)
    return True


@graphql_mutation.field("revoke_affiliation")
@graphql_payload
@require_authentication
async def revoke_affiliation(
        _,
        info,
        user: int,
        team: int,
        access: Access
) -> bool:
    agent_id = info.context.get('user_id')
    logger.debug(f"Agent {agent_id} removing {access} for team: {team} for user {user}")
    cmd = RevokeAffiliation(
        agent=agent_id,
        user=user,
        team=team,
        access=access
    )
    await info.context['bus'].handle(cmd)
    return True