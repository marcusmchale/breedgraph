import pytest
import asyncio
import pytest_asyncio

from asgi_lifespan import LifespanManager
from httpx import AsyncClient, ASGITransport
from fastapi import FastAPI
from typing import AsyncIterator
from itsdangerous import URLSafeTimedSerializer

from tests.e2e.payload_helpers import get_verified_payload
from tests.e2e.accounts.post_methods import (
    post_to_add_first_account,
    post_to_verify_email,
    post_to_login
)

from src.breedgraph.main import app
from src.breedgraph.entrypoints.fastapi.graphql.decorators import GQLStatus
from src.breedgraph.config import SECRET_KEY, VERIFY_TOKEN_SALT, TEST_EMAILS,  get_base_url
from src.breedgraph.custom_exceptions import (
    UnauthorisedOperationError,
    IllegalOperationError,
    IdentityExistsError,
    ProtectedNodeError,
    ProtectedRelationshipError
)

FIRST_USER = {
    "name": "First User",
    "email": TEST_EMAILS[0],
    "password": "First Password"
}

SECOND_USER = {
    "name": "Second User",
    "email": TEST_EMAILS[1],
    "password": "Second Password"
}

FIRST_TEAM = "First Team"
SECOND_TEAM = "Second Team"


@pytest_asyncio.fixture(scope="session")
async def test_app() -> FastAPI:
    async with LifespanManager(app) as manager:
            yield manager.app

@pytest_asyncio.fixture(scope="session")
async def client(test_app: FastAPI) -> AsyncIterator[AsyncClient]:
        transport = ASGITransport(app=test_app)
        async with AsyncClient(transport=transport, base_url=get_base_url()) as client:
            yield client

@pytest.mark.asyncio(scope="session")
async def test_first_account_on_empty(client):
    response = await post_to_add_first_account(
        client,
        FIRST_USER["name"],
        FIRST_USER["email"],
        FIRST_USER["password"],
        FIRST_TEAM
    )
    payload = get_verified_payload(response, "add_first_account")
    assert payload['status'] == GQLStatus.SUCCESS.name
    assert payload['errors'] is None
    assert payload['result']

@pytest.mark.asyncio(scope="session")
async def test_second_account_to_first_should_fail(client):
    response = await post_to_add_first_account(
        client,
        SECOND_USER["name"],
        SECOND_USER["email"],
        SECOND_USER["password"],
        SECOND_TEAM
    )
    payload = get_verified_payload(response, "add_first_account")
    assert payload['status'] == GQLStatus.ERROR.name
    assert payload['result'] is None
    for error in payload['errors']:
        assert error['name'] == IdentityExistsError.__name__

@pytest.mark.asyncio(scope="session")
async def test_login_should_fail_if_not_verified(client):
    response = await post_to_login(client,"First User", "First Password")
    payload = get_verified_payload(response, "login")
    assert payload['status'] == GQLStatus.ERROR.name
    assert payload['result'] is None
    for error in payload['errors']:
        assert error['name'] == UnauthorisedOperationError.__name__

#@pytest.mark.asyncio(scope="session")
#async def test_verify_email(client):
#    token = URLSafeTimedSerializer(SECRET_KEY).dumps(1, salt=VERIFY_TOKEN_SALT)
#    response = await post_to_verify_email(client, token)
#    payload = get_verified_payload(response, "verify_email")
#    assert payload['status'] == GQLStatus.SUCCESS.name
#    assert payload['errors'] is None
#    assert payload['result']

#@pytest.mark.asyncio
#async def test_login_should_succeed(client):
#    response = await post_to_login(client, "First User", "First Password")
#    import pdb;
#    pdb.set_trace()

# @pytest.mark.asyncio
# async def test_login_should_fail_if_not_username(client):
#    response = await post_to_login(client,"First User", "First Password")
#    import pdb; pdb.set_trace()
#
# @pytest.mark.asyncio
# async def test_login_should_fail_if_not_password(client):
#    response = await post_to_login(client,"First User", "First Password")
#    import pdb; pdb.set_trace()
#


#@pytest.mark.asyncio
#async def test_login():
#    response = await post_to_login("First User", "First Password")
#    import pdb; pdb.set_trace()

#async def add_account(name: str, email: str):
#    response = await post_to_add_account(name, email)
#    payload = get_verified_payload(response, "add_account")
#    assert payload['status'] == GQLStatus.SUCCESS.name
#    assert payload['errors'] is None
#    assert payload['result']
#
#@pytest.mark.asyncio
#async def test_add_account():
#    await add_account('test', '')
#
#@pytest.mark.asyncio
#async def test_add_account_same_name_fails():
#    name = 'test2'
#    email = ''
#    await add_account(name, email)
#
#    response = await post_to_add_account(name, email)
#    payload = get_verified_payload(response, "add_account")
#    assert payload['status'] == GQLStatus.ERROR.name
#    assert payload['result'] is None
#    for error in payload['errors']:
#        assert error['name'] == 'IdentityExistsError'
#
##@pytest.mark.asyncio
##async def test_get_teams():
##    async with httpx.AsyncClient(app=app) as client:
##        response = await client.post(
##            url=get_gql_url(),
##            json={
#                "query": (
#                    " query { get_teams "
#                    "  { "
#                    "    status, "
#                    "    result { id, name, fullname }, "
#                    "    errors { name, message } "
#                    "  } "
#                    " } "
#                )
#            }
#        )
#        payload = get_verified_payload(response, "get_teams")
#        assert payload['status'] == GQLStatus.SUCCESS.name
#        assert payload['errors'] is None
#        for team in payload['result']:
#            TeamBase(**team)







