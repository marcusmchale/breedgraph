import pytest
import httpx

from asgi_lifespan import LifespanManager

from src.breedgraph.config import get_gql_url
from src.breedgraph.entrypoints.fastapi.graphql.decorators import GQLStatus
from tests.e2e.payload_helpers import get_verified_payload

from src.breedgraph.entrypoints.fastapi import app

async def post_to_add_first_account():
    json={
        "query": (
            " mutation ( "
            "  $name: String!,"
            "  $fullname: String,"
            "  $email: String!,"
            "  $password: String!,"
            "  $team_name: String!,"
            "  $team_fullname: String"
            " ) { "
            "  add_first_account( "
            "    name: $name, "
            "    fullname: $fullname, "
            "    email: $email, "
            "    password: $password, "
            "    team_name: $team_name, "
            "    team_fullname: $team_fullname"
            "  ) { "
            "    status, "
            "    result, "
            "    errors { name, message } "
            "  } "
            " } "
        ),
        "variables": {
            "name": "First User",
            "fullname": "First BreedGraph User",
            "email": "marcusmchale@gmail.com",
            "password": "password",
            "team_name": "First Team",
            "team_fullname": "The First Team"
        }
    }
    async with LifespanManager(app):
        transport = httpx.ASGITransport(app=app)
        async with httpx.AsyncClient(transport=transport) as client:
            return await client.post(get_gql_url(), json=json)

async def first_account_on_empty():
    response = await post_to_add_first_account()
    payload = get_verified_payload(response, "add_first_account")
    assert payload['status'] == GQLStatus.SUCCESS.name
    assert payload['errors'] is None
    assert payload['result']

async def second_account_should_fail():
    response = await post_to_add_first_account()
    payload = get_verified_payload(response, "add_first_account")
    assert payload['status'] == GQLStatus.ERROR.name
    assert payload['result'] is None
    for error in payload['errors']:
        assert error['name'] == 'IdentityExistsError'

@pytest.mark.asyncio
async def test_create_first_only():
    await first_account_on_empty()
    await second_account_should_fail()

async def post_to_add_email(name: str, email: str):
    json={
        "query": (
            " mutation ( "
            "  $name: String!,"
            "  $fullname: String,"
            "  $email: String!,"
            "  $password: String!"
            " ) { "
            "  add_account( "
            "    name: $name, "
            "    fullname: $fullname, "
            "    email: $email, "
            "    password: $password "
            "  ) { "
            "    status, "
            "    result, "
            "    errors { name, message } "
            "  } "
            " } "
        ),
        "variables": {
            "name": f"{name}",
            "fullname": f"{name}",
            "email": f"{email}",
            "password": "password"
        }
    }
    async with LifespanManager(app):
        transport = httpx.ASGITransport(app=app)
        async with httpx.AsyncClient(transport=transport) as client:
            return await client.post(get_gql_url(), json=json)

@pytest.mark.asyncio
async def test_add_email():



async def post_to_add_account(name: str, email: str):
    json={
        "query": (
            " mutation ( "
            "  $name: String!,"
            "  $fullname: String,"
            "  $email: String!,"
            "  $password: String!"
            " ) { "
            "  add_account( "
            "    name: $name, "
            "    fullname: $fullname, "
            "    email: $email, "
            "    password: $password "
            "  ) { "
            "    status, "
            "    result, "
            "    errors { name, message } "
            "  } "
            " } "
        ),
        "variables": {
            "name": f"{name}",
            "fullname": f"{name}",
            "email": f"{email}",
            "password": "password"
        }
    }
    async with LifespanManager(app):
        transport = httpx.ASGITransport(app=app)
        async with httpx.AsyncClient(transport=transport) as client:
            return await client.post(get_gql_url(), json=json)

async def add_account(name: str, email: str):
    response = await post_to_add_account(name, email)
    payload = get_verified_payload(response, "add_account")
    assert payload['status'] == GQLStatus.SUCCESS.name
    assert payload['errors'] is None
    assert payload['result']

@pytest.mark.asyncio
async def test_add_account():
    await add_account('test', '')

@pytest.mark.asyncio
async def test_add_account_same_name_fails():
    name = 'test2'
    email = ''
    await add_account(name, email)

    response = await post_to_add_account(name, email)
    payload = get_verified_payload(response, "add_account")
    assert payload['status'] == GQLStatus.ERROR.name
    assert payload['result'] is None
    for error in payload['errors']:
        assert error['name'] == 'IdentityExistsError'

#@pytest.mark.asyncio
#async def test_get_teams():
#    async with httpx.AsyncClient(app=app) as client:
#        response = await client.post(
#            url=get_gql_url(),
#            json={
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







