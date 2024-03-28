import httpx
import pytest

from src.breedgraph.entrypoints.fastapi.__init__ import app
from src.breedgraph.config import get_gql_url
from src.breedgraph.domain.model.accounts import TeamBase

from src.breedgraph.entrypoints.fastapi.graphql.decorators import GQLStatus

from tests.e2e.payload_helpers import get_verified_payload


async def post_to_allowed_email(email):
    async with httpx.AsyncClient(app=app) as client:
        return await client.post(
            url=get_gql_url(),
            json={
                "query": (
                    " query($email: String!) { allowed_email (email: $email) "
                    "  { "
                    "    status, "
                    "    result, "
                    "    errors { name, message } "
                    "  } "
                    " } "
                ),
                "variables": {"email": email}
            }
        )


@pytest.mark.asyncio
async def test_allowed_email():
    response = await post_to_allowed_email("")
    payload = get_verified_payload(response, "allowed_email")
    assert payload['status'] == GQLStatus.NOT_FOUND.name
    assert payload['errors'] is None
    assert payload['result'] is False


@pytest.mark.asyncio
async def test_get_teams():
    async with httpx.AsyncClient(app=app) as client:
        response = await client.post(
            url=get_gql_url(),
            json={
                "query": (
                    " query { get_teams "
                    "  { "
                    "    status, "
                    "    result { id, name, fullname }, "
                    "    errors { name, message } "
                    "  } "
                    " } "
                )
            }
        )
        payload = get_verified_payload(response, "get_teams")
        assert payload['status'] == GQLStatus.SUCCESS.name
        assert payload['errors'] is None
        for team in payload['result']:
            TeamBase(**team)







