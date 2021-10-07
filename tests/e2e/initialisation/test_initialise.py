import httpx
import pytest
import os

from src.dbtools.config import get_gql_url
from src.dbtools.entrypoints.fastapi.graphql.decorators import GQLStatus
from tests.e2e.payload_helpers import get_verified_payload

os.environ["DATABASE_NAME"] = "testing"

from src.dbtools.entrypoints.fastapi.main import app


async def post_to_initialise():
    async with httpx.AsyncClient(app=app, base_url=get_gql_url()) as client:
        return await client.post(
            url=get_gql_url(),
            json={
                "query": (
                    " mutation ( "
                    "  $team_name: String!,"
                    "  $team_fullname: String!,"
                    "  $name: String!,"
                    "  $user_fullname: String!,"
                    "  $password: String!,"
                    "  $email: String!"
                    " ) { "
                    "  initialise( "
                    "    team_name: $team_name, "
                    "    team_fullname: $team_fullname, "
                    "    name: $name, "
                    "    user_fullname: $user_fullname, "
                    "    password: $password, "
                    "    email: $email "
                    "  ) { "
                    "    status, "
                    "    result, "
                    "    errors { name, message } "
                    "  } "
                    " } "
                ),
                "variables": {
                    "team_name": "LTN",
                    "team_fullname": "Long Team Name",
                    "name": "NewUser",
                    "user_fullname": "New Database User",
                    "password": "CREATIVE_PASSWORD",
                    "email": ""
                }
            }
        )


@pytest.mark.asyncio
async def test_initialise_on_empty():
    response = await post_to_initialise()
    payload = get_verified_payload(response, "initialise")
    assert payload['status'] == GQLStatus.SUCCESS.name
    assert payload['errors'] is None
    assert payload['result']


@pytest.mark.asyncio
async def test_initialise_should_fail():
    response = await post_to_initialise()
    payload = get_verified_payload(response, "initialise")
    assert payload['status'] == GQLStatus.ERROR.name
    assert payload['result'] is None
    for error in payload['errors']:
        assert error['name'] == 'IdentityExistsError'

