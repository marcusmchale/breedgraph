import pytest
import pytest_asyncio

from tests.e2e.payload_helpers import get_verified_payload
from tests.e2e.accounts.post_methods import (
    post_to_add_first_account,
    post_to_verify_email,
    post_to_login,
    post_to_add_email,
    post_to_add_account,
    post_to_add_team,
    post_to_request_read
)
from tests.e2e.accounts.gmail_fetching import confirm_email_delivered_to_gmail, get_json_from_gmail

from src.breedgraph.entrypoints.fastapi.graphql.decorators import GQLStatus


def assert_payload_success(payload):
    assert payload['status'] == GQLStatus.SUCCESS.name
    assert payload['errors'] is None
    assert payload['result']


async def check_verify_email(client, mailto: str):
    json_content = await get_json_from_gmail(mailto=mailto)
    token = json_content['token']
    response = await post_to_verify_email(client, token)
    assert_payload_success(get_verified_payload(response, "verify_email"))

@pytest.mark.usefixtures("session_database")
@pytest.mark.asyncio(scope="session")
async def test_first_user_registers_and_verifies(client, user_input_generator):

    first_user_input = user_input_generator.new_user_input()
    response = await post_to_add_first_account(
        client,
        first_user_input["name"],
        first_user_input["email"],
        first_user_input["password"],
        first_user_input["team_name"]
    )
    assert_payload_success(get_verified_payload(response, "add_first_account"))

    await check_verify_email(client, first_user_input['email'])

@pytest_asyncio.fixture(scope="session")
async def first_user_login_token(client, user_input_generator) -> str:
    first_user_input = user_input_generator.user_inputs[0]

    login_response = await post_to_login(
        client,
        first_user_input["name"],
        first_user_input["password"],
    )
    login_payload = get_verified_payload(login_response, "login")
    assert_payload_success(login_payload)
    yield login_payload['result']['access_token']

@pytest.mark.usefixtures("session_database")
@pytest.mark.asyncio(scope="session")
async def test_second_user_invited_registers_and_verifies(client, user_input_generator, first_user_login_token):
    # first user invites the second by adding an email address to their allowed list
    second_user_input = user_input_generator.new_user_input()
    invite_response = await post_to_add_email(
        client,
        first_user_login_token,
        second_user_input["email"]
    )
    invite_payload = get_verified_payload(invite_response, "add_email")
    assert_payload_success(invite_payload)
    assert await confirm_email_delivered_to_gmail(second_user_input["email"])

    # second user can then register
    register_response = await post_to_add_account(
        client,
        second_user_input["name"],
        second_user_input["email"],
        second_user_input["password"]
    )
    register_payload = get_verified_payload(register_response, "add_account")
    assert_payload_success(register_payload)

    await check_verify_email(client, second_user_input['email'])

@pytest.mark.asyncio(scope="session")
async def test_first_user_adds_teams(client, user_input_generator, first_user_login_token):
    second_user_input = user_input_generator.user_inputs[1]
    add_team_response = await post_to_add_team(
        client,
        first_user_login_token,
        second_user_input['team_name']
    )
    add_team_payload = get_verified_payload(add_team_response, "add_team")
    assert_payload_success(add_team_payload)

    add_child_team_response = await post_to_add_team(
        client,
        first_user_login_token,
        user_input_generator.new_user_input()['team_name'],
        1
    )
    add_child_team_payload = get_verified_payload(add_child_team_response, "add_team")
    assert_payload_success(add_child_team_payload)


@pytest_asyncio.fixture(scope="session")
async def second_user_login_token(client, user_input_generator) -> str:
    second_user_input = user_input_generator.user_inputs[0]

    login_response = await post_to_login(
        client,
        second_user_input["name"],
        second_user_input["password"],
    )
    login_payload = get_verified_payload(login_response, "login")
    assert_payload_success(login_payload)
    yield login_payload['result']['access_token']

@pytest.mark.asyncio(scope="session")
async def test_second_user_requests_read(client, user_input_generator, second_user_login_token):
    admin_user_input = user_input_generator.user_inputs[0]

    team_id = 2
    read_request_response = await post_to_request_read(
        client,
        second_user_login_token,
        team_id
    )
    request_read_payload = get_verified_payload(read_request_response, "request_read")
    assert_payload_success(request_read_payload)

    assert await confirm_email_delivered_to_gmail(admin_user_input["email"])


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







