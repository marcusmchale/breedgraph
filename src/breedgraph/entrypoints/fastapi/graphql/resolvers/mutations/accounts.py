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


from src.breedgraph.config import LOGIN_EXPIRES

import logging
logger = logging.getLogger(__name__)

from . import graphql_mutation

@graphql_mutation.field("accountsCreateAccount")
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

@graphql_mutation.field("accountsRequestPasswordReset")
@graphql_payload
async def request_change_password(
        _,
        info,
        email: str
) -> bool:
    logger.debug(f"Request change password for email: {email}")
    await info.context['bus'].handle(PasswordChangeRequested(email=email))
    return True

@graphql_mutation.field("accountsResetPassword")
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

    async with info.context['bus'].uow.get_uow() as uow:
        account = await uow.repositories.accounts.get(user_id=user_id)
        if not account:
            raise UnauthorisedOperationError("Token not valid because user was not found")
        logger.debug(f"Change password for user: {account.user.id}")
        password_hash = bcrypt.hashpw(password.encode(), bcrypt.gensalt()).decode()

    cmd = UpdateUser(user_id=user_id, password_hash=password_hash)
    await info.context['bus'].handle(cmd)
    return True

@graphql_mutation.field("accountsLogin")
@graphql_payload
async def login(
        _,
        info,
        username: str,
        password: str
) -> bool:
    logger.debug(f"Log in: {username}")
    fail_message = "Invalid username or password"

    brute_force_service = info.context.get('brute_force_service')
    if brute_force_service:
        # Check if locked out
        if await brute_force_service.is_locked_out(username):
            ttl = await brute_force_service.get_lockout_ttl(username)
            logger.warning(f"Login attempt blocked for locked out user: {username}")
            raise UnauthorisedOperationError(
                f"Too many failed attempts. Please try again in {ttl} seconds."
            )

        remaining = await brute_force_service.get_remaining_attempts(username)
        logger.debug(f"Login attempt for {username}, remaining attempts: {remaining}")

    async with info.context['bus'].uow.get_uow() as uow:
        account = await uow.repositories.accounts.get(name=username)
        if not account:
            # Record failed attempt even if user doesn't exist (prevents user enumeration timing attacks)
            if brute_force_service:
                await brute_force_service.record_failed_attempt(username)
            raise UnauthorisedOperationError(fail_message)

        # failsafe against access to the system account
        if not account.user.password_hash or account.user.password_hash.strip() == "":
            if brute_force_service:
                await brute_force_service.record_failed_attempt(username)
            raise UnauthorisedOperationError(fail_message)

        if bcrypt.checkpw(password.encode(), account.user.password_hash.encode()):
            if not account.user.email_verified:
                raise UnauthorisedOperationError("Please confirm email before logging in")

            # Successful login - clear failed attempts
            if brute_force_service:
                await brute_force_service.record_successful_attempt(username)

            await info.context['bus'].handle(Login(user_id=account.user.id))
            token = info.context['auth_service'].create_login_token(account.user.id)

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
            # Failed password check
            if brute_force_service:
                await brute_force_service.record_failed_attempt(username)
            raise UnauthorisedOperationError(fail_message)


@graphql_mutation.field("accountsLogout")
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


@graphql_mutation.field("accountsUpdateUser")
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
        user_id=user_id,
        name=name,
        fullname=fullname,
        password_hash=password_hash,
        email=email
    )
    await info.context['bus'].handle(cmd)
    return True

# the below also has a dedicated endpoint for REST so can follow a simple link
@graphql_mutation.field("accountsVerifyEmail")
@graphql_payload
async def verify_email(
        _,
        info,
        token: str
) -> bool:
    logger.debug(f"Verify email")
    await info.context['bus'].handle(VerifyEmail(token=token))
    return True

@graphql_mutation.field("accountsAddEmail")
@graphql_payload
@require_authentication
async def add_email(_, info, email: str) -> bool:
    user_id = info.context.get('user_id')
    logger.debug(f"Add email ({email}) to allowed emails for user {user_id}")
    await info.context['bus'].handle(AddEmail(user_id=user_id, email=email))
    return True

@graphql_mutation.field("accountsRemoveEmail")
@graphql_payload
@require_authentication
async def remove_email(_, info, email: str) -> bool:
    user_id = info.context.get('user_id')
    logger.debug(f"Remove email ({email}) from allowed emails for user {user_id}")
    await info.context['bus'].handle(RemoveEmail(user_id=user_id, email=email))
    return True

@graphql_mutation.field("accountsRequestAffiliation")
@graphql_payload
@require_authentication
async def request_affiliation(
        _,
        info,
        team_id: int,
        access: Access,
        heritable: bool = True
        # most requests should be heritable to allow an admin to authorise to a child team
        # however, since authorisation is automatic for admins,
        # the admin may wish to specify a non heritable affiliation
) -> bool:
    user_id = info.context.get('user_id')
    logger.debug(f"User {user_id} requests {access.value} for team: {team_id}")
    cmd = RequestAffiliation(
        user_id=user_id,
        team_id=team_id,
        access=access,
        heritable=heritable
    )
    await info.context['bus'].handle(cmd)
    return True

@graphql_mutation.field("accountsApproveAffiliation")
@graphql_payload
@require_authentication
async def approve_affiliation(
        _,
        info,
        user_id: int,
        team_id: int,
        access: Access,
        heritable: bool = False
) -> bool:
    agent_id = info.context.get('user_id')
    logger.debug(f"Agent {agent_id} approving {access.value} to team {team_id} for user {user_id}")
    cmd = ApproveAffiliation(
        agent_id=agent_id,
        user_id=user_id,
        team_id=team_id,
        access=access,
        heritable=heritable
    )
    await info.context['bus'].handle(cmd)
    return True

@graphql_mutation.field("accountsRemoveAffiliation")
@graphql_payload
@require_authentication
async def remove_affiliation(
        _,
        info,
        team_id: int,
        access: Access
) -> bool:
    agent_id = info.context.get('user_id')
    logger.debug(f"Agent {agent_id} removing {access.value} for team: {team_id}")
    cmd = RemoveAffiliation(
        agent_id=agent_id,
        user_id=agent_id,
        team_id=team_id,
        access=access
    )
    await info.context['bus'].handle(cmd)
    return True


@graphql_mutation.field("accountsRevokeAffiliation")
@graphql_payload
@require_authentication
async def revoke_affiliation(
        _,
        info,
        user_id: int,
        team_id: int,
        access: Access
) -> bool:
    agent_id = info.context.get('user_id')
    logger.debug(f"Agent {agent_id} removing {access.value} for team: {team_id} for user {user_id}")
    cmd = RevokeAffiliation(
        agent_id=agent_id,
        user_id=user_id,
        team_id=team_id,
        access=access
    )
    await info.context['bus'].handle(cmd)
    return True