import httpx
import pytest

from src.dbtools.entrypoints.fast_api.main import app
from src.dbtools.config import get_gql_url, pwd_context
from src.dbtools.domain.commands.accounts import Initialise
from src.dbtools.entrypoints.fast_api.graphql.decorators import GQLStatus


@pytest.mark.asyncio
async def test_initialise():
    command = Initialise(
        team_name="NUIG",
        team_fullname="National University of Ireland, Galway",
        username="Marcus",
        user_fullname="Marcus McHale",
        password_hash=pwd_context.hash("PASSWORD"),
        email="marcus.mchale@nuigalway.ie"
    )
    async with httpx.AsyncClient(app=app, base_url=get_gql_url()) as client:
        response = await client.post(
            url=get_gql_url(),
            data={
                "query": (
                    "mutation { "
                    "  initialise("
                    "  team_name: $team_name "

                    "  ) "
                    " "
                ),
                "variables": command
            }
        )
        assert response["status"] == GQLStatus.SUCCESS
        assert response.result