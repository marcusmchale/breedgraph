"""
Changing a password, or the email address that resets it, asks for the current password, so that whoever holds a
signed-in browser can't take the account over. A changed password ends the user's sign-ins: a login token signed before
it no longer signs in, while the browser that changed it is signed in again; and a password reset link holds only
until the password changes, as on its first use. Tokens are signed to the second, so the tests wait a second before
changing the password.
"""
import asyncio
from http.cookies import SimpleCookie

import pytest
from itsdangerous import URLSafeTimedSerializer

from breedgraph import config
from breedgraph.config import GQL_API_PATH

from tests.breedgraph.e2e.utils import with_auth, get_verified_payload, assert_payload_success
from tests.breedgraph.scenarios.account_builder import AccountBuilder
from tests.breedgraph.utilities.inputs import UserInputGenerator

NEW_PASSWORD = 'A-new-Passw0rd!'
ACCOUNT = "query { accountsAccount { status result { user { id } } errors { message } } }"
UPDATE_PASSWORD = (
    "mutation ( $password: String, $current: String ) { "
    "  accountsUpdateUser( password: $password, currentPassword: $current ) { status, result, errors { message } } "
    "}"
)
RESET_PASSWORD = (
    "mutation ( $token: String!, $password: String! ) { "
    "  accountsResetPassword( token: $token, password: $password ) { status, result, errors { message } } "
    "}"
)


async def post(client, token: str | None, query: str, variables: dict | None = None):
    headers = with_auth(csrf_token=client.headers["X-CSRF-Token"], auth_token=token)
    return await client.post(GQL_API_PATH, json={"query": query, "variables": variables or {}}, headers=headers)


async def signed_in(client, token: str) -> int | None:
    """Whom the token signs in, if anyone"""
    payload = get_verified_payload(await post(client, token, ACCOUNT), 'accountsAccount')
    return int(payload['result']['user']['id']) if payload['result'] else None


async def account_with_password(uow_factory) -> tuple[int, str]:
    """An account and its password, which a change of password asks for"""
    user_input = UserInputGenerator().new_user_input()
    account = AccountBuilder.account_input()
    account.user.password_hash = user_input['password_hash']
    async with uow_factory.get_uow() as uow:
        stored = await uow.repositories.accounts.create(account)
        await uow.commit()
    return stored.user.id, user_input['password']


def login_cookie(response) -> str | None:
    for header in response.headers.get_list('set-cookie'):
        morsel = SimpleCookie(header).get(config.cookie_name('auth_token'))
        if morsel is not None:
            return morsel.value
    return None


@pytest.mark.asyncio(loop_scope="session")
async def test_a_changed_password_ends_the_other_sign_ins_and_renews_the_one_that_changed_it(
        client, uow_factory, login_token_factory, isolated_state
):
    user_id, password = await account_with_password(uow_factory)
    this_browser = login_token_factory(user_id)
    assert await signed_in(client, this_browser) == user_id
    await asyncio.sleep(1.1)
    other_browser = login_token_factory(user_id)

    await asyncio.sleep(1.1)
    response = await post(client, this_browser, UPDATE_PASSWORD, {"password": NEW_PASSWORD, "current": password})
    assert_payload_success(get_verified_payload(response, 'accountsUpdateUser'))
    renewed = login_cookie(response)

    assert await signed_in(client, other_browser) is None
    assert await signed_in(client, this_browser) is None
    assert await signed_in(client, renewed) == user_id


@pytest.mark.asyncio(loop_scope="session")
async def test_a_reset_link_holds_until_the_password_changes(client, uow_factory, login_token_factory, isolated_state):
    user_id = await AccountBuilder(uow_factory).account()
    before = login_token_factory(user_id)
    link = URLSafeTimedSerializer(config.SECRET_KEY).dumps(user_id, salt=config.PASSWORD_RESET_SALT)

    await asyncio.sleep(1.1)
    response = await post(client, None, RESET_PASSWORD, {"token": link, "password": NEW_PASSWORD})
    assert_payload_success(get_verified_payload(response, 'accountsResetPassword'))
    assert await signed_in(client, before) is None

    response = await post(client, None, RESET_PASSWORD, {"token": link, "password": 'Another-Passw0rd!'})
    payload = get_verified_payload(response, 'accountsResetPassword')
    assert payload['status'] == 'ERROR'
    assert 'before the password last changed' in payload['errors'][0]['message']


@pytest.mark.asyncio(loop_scope="session")
async def test_a_changed_name_keeps_the_sign_ins(client, uow_factory, login_token_factory, isolated_state):
    user_id = await AccountBuilder(uow_factory).account()
    token = login_token_factory(user_id)
    await asyncio.sleep(1.1)
    response = await post(
        client, token, "mutation { accountsUpdateUser( fullname: \"Renamed\" ) { status, result, errors { message } } }"
    )
    assert_payload_success(get_verified_payload(response, 'accountsUpdateUser'))
    assert login_cookie(response) is None
    assert await signed_in(client, token) == user_id


UPDATE_EMAIL = (
    "mutation ( $email: String, $current: String ) { "
    "  accountsUpdateUser( email: $email, currentPassword: $current ) { status, result, errors { message } } "
    "}"
)


def refusal(response, query_name='accountsUpdateUser') -> str:
    payload = get_verified_payload(response, query_name)
    assert payload['status'] == 'ERROR'
    return payload['errors'][0]['message']


@pytest.mark.asyncio(loop_scope="session")
async def test_a_new_password_or_email_asks_for_the_current_password(
        client, uow_factory, login_token_factory, isolated_state
):
    user_id, password = await account_with_password(uow_factory)
    token = login_token_factory(user_id)
    asking = "Give your current password to change your password or email address"

    assert refusal(await post(client, token, UPDATE_PASSWORD, {"password": NEW_PASSWORD})) == asking
    assert refusal(await post(client, token, UPDATE_EMAIL, {"email": "someone.else@example.org"})) == asking
    wrong = {"password": NEW_PASSWORD, "current": password + "x"}
    assert refusal(await post(client, token, UPDATE_PASSWORD, wrong)) == "Incorrect password"
    async with uow_factory.get_uow() as uow:
        account = await uow.repositories.accounts.get(user_id=user_id)
    assert account.user.sign_ins_ended_at is None
    assert await signed_in(client, token) == user_id

    # the address the user has already, as a form sends it with the rest, asks for nothing
    response = await post(
        client, token,
        "mutation ( $email: String ) { accountsUpdateUser( fullname: \"Renamed\", email: $email ) "
        "{ status, result, errors { message } } }",
        {"email": account.user.email}
    )
    assert_payload_success(get_verified_payload(response, 'accountsUpdateUser'))
    response = await post(client, token, UPDATE_EMAIL, {"email": "someone.else@example.org", "current": password})
    assert_payload_success(get_verified_payload(response, 'accountsUpdateUser'))
