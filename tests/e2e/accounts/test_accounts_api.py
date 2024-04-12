import pytest
import asyncio
import pytest_asyncio

from itsdangerous import URLSafeTimedSerializer

from tests.e2e.payload_helpers import get_verified_payload
from tests.e2e.accounts.post_methods import (
    post_to_add_first_account,
    post_to_verify_email,
    post_to_login,
    post_to_add_email,
    post_to_remove_email,
    post_to_add_account,
    post_to_add_team
)

from src.breedgraph.entrypoints.fastapi.graphql.decorators import GQLStatus
from src.breedgraph.config import (
    SECRET_KEY,
    VERIFY_TOKEN_SALT,
    MAIL_USERNAME,
    MAIL_DOMAIN,
    get_base_url
)

from src.breedgraph.custom_exceptions import (
    UnauthorisedOperationError,
    IllegalOperationError,
    IdentityExistsError,
    ProtectedNodeError,
    ProtectedRelationshipError
)


@pytest.mark.usefixtures('clear_database')
@pytest.mark.asyncio(scope="session")
async def test_first_account_on_empty(client, user_input_generator):
    first_user_input = user_input_generator.new_user_input()
    response = await post_to_add_first_account(
        client,
        first_user_input["name"],
        first_user_input["email"],
        first_user_input["password"],
        first_user_input["team"]
    )
    payload = get_verified_payload(response, "add_first_account")
    assert payload['status'] == GQLStatus.SUCCESS.name
    assert payload['errors'] is None
    assert payload['result']

#@pytest.mark.asyncio(scope="session")
#async def test_second_account_to_first_should_raise_unauthorised(client, user_input_generator):
#    second_user_input = user_input_generator.new_user_input()
#    response = await post_to_add_first_account(
#        client,
#        second_user_input["name"],
#        second_user_input["email"],
#        second_user_input["password"],
#        second_user_input["team"]
#    )
#    payload = get_verified_payload(response, "add_first_account")
#    assert payload['status'] == GQLStatus.ERROR.name
#    assert payload['result'] is None
#    for error in payload['errors']:
#        assert error['name'] == UnauthorisedOperationError.__name__
#
#@pytest.mark.asyncio(scope="session")
#async def test_login_if_not_verified_should_raise_unauthorised(client, user_input_generator):
#    first_user_input = user_input_generator.user_inputs[0]
#    response = await post_to_login(
#        client,
#        first_user_input["name"],
#        first_user_input["password"]
#    )
#    payload = get_verified_payload(response, "login")
#    assert payload['status'] == GQLStatus.ERROR.name
#    assert payload['result'] is None
#    for error in payload['errors']:
#        assert error['name'] == UnauthorisedOperationError.__name__
#
#@pytest.mark.asyncio(scope="session")
#async def test_verify_email_should_succeed(client):
#    token = URLSafeTimedSerializer(SECRET_KEY).dumps(1, salt=VERIFY_TOKEN_SALT)
#    response = await post_to_verify_email(client, token)
#    payload = get_verified_payload(response, "verify_email")
#    assert payload['status'] == GQLStatus.SUCCESS.name
#    assert payload['errors'] is None
#    assert payload['result']
#
#@pytest.mark.asyncio(scope="session")
#async def test_login_should_succeed(client, user_input_generator):
#    first_user_input = user_input_generator.user_inputs[0]
#    response = await post_to_login(
#        client,
#        first_user_input["name"],
#        first_user_input["password"],
#    )
#    payload = get_verified_payload(response, "login")
#    assert payload['status'] == GQLStatus.SUCCESS.name
#    assert payload['errors'] is None
#    assert payload['result']['access_token'] is not None
#    assert payload['result']['token_type'] == 'bearer'
#
#@pytest.mark.asyncio(scope="session")
#async def test_login_wrong_username_should_raise_unauthorised(client, user_input_generator):
#    first_user_input = user_input_generator.user_inputs[0]
#    response = await post_to_login(
#        client,
#        first_user_input["name"] + "NOT_NAME",
#        first_user_input["password"]
#    )
#    payload = get_verified_payload(response, "login")
#    assert payload['status'] == GQLStatus.ERROR.name
#    assert payload['result'] is None
#    for error in payload['errors']:
#        assert error['name'] == UnauthorisedOperationError.__name__
#
#@pytest.mark.asyncio(scope="session")
#async def test_login_with_wrong_password_should_raise_unauthorised(client, user_input_generator):
#    first_user_input = user_input_generator.user_inputs[0]
#    response = await post_to_login(
#        client,
#        first_user_input['name'],
#        first_user_input['password'] + "NOT_PASSWORD"
#    )
#    payload = get_verified_payload(response, "login")
#    assert payload['status'] == GQLStatus.ERROR.name
#    assert payload['result'] is None
#    for error in payload['errors']:
#        assert error['name'] == UnauthorisedOperationError.__name__
#
#@pytest_asyncio.fixture(scope="session")
#async def token(client, user_input_generator) -> str:
#    first_user_input = user_input_generator.user_inputs[0]
#    response = await post_to_login(
#        client,
#        first_user_input['name'],
#        first_user_input['password']
#    )
#    payload = get_verified_payload(response, "login")
#    yield payload['result']['access_token']
#
#@pytest.mark.asyncio(scope="session")
#async def test_add_and_remove_email_should_succeed(client, token, user_input_generator):
#    second_user_input = user_input_generator.user_inputs[1]
#    await test_add_email_should_succeed()
#    response = await post_to_remove_email(
#        client,
#        token,
#        second_user_input["email"]
#    )
#    payload = get_verified_payload(response, "remove_email")
#    assert payload['status'] == GQLStatus.SUCCESS.name
#    assert payload['errors'] is None
#    assert payload['result']
#
#@pytest.mark.asyncio(scope="session")
#async def test_add_email_should_succeed(client, token, user_input_generator):
#    second_user_input = user_input_generator.user_inputs[1]
#    response = await post_to_add_email(
#        client,
#        token,
#        second_user_input["email"]
#    )
#    payload = get_verified_payload(response, "add_email")
#    assert payload['status'] == GQLStatus.SUCCESS.name
#    assert payload['errors'] is None
#    assert payload['result']
#
#@pytest.mark.asyncio(scope="session")
#async def test_add_account_without_allowed_email_should_raise_unauthorised(client, user_input_generator):
#    second_user_input = user_input_generator.user_inputs[1]
#    response = await post_to_add_account(
#        client,
#        second_user_input["name"],
#        second_user_input["email"] + "NOT_EMAIL",
#        second_user_input["password"]
#    )
#    payload = get_verified_payload(response, "add_account")
#    assert payload['status'] == GQLStatus.ERROR.name
#    assert payload['result'] is None
#    for error in payload['errors']:
#        assert error['name'] == UnauthorisedOperationError.__name__
#
#@pytest.mark.asyncio(scope="session")
#async def test_add_second_account_same_name_should_raise_identity_exists(client, user_input_generator):
#    first_user_input = user_input_generator.user_inputs[0]
#    second_user_input = user_input_generator.user_inputs[1]
#    response = await post_to_add_account(
#        client,
#        first_user_input["name"],
#        second_user_input["email"],
#        second_user_input["password"]
#    )
#    payload = get_verified_payload(response, "add_account")
#    assert payload['status'] == GQLStatus.ERROR.name
#    assert payload['result'] is None
#    for error in payload['errors']:
#        assert error['name'] == IdentityExistsError.__name__
#
#@pytest.mark.asyncio(scope="session")
#async def test_add_second_account_should_succeed(client):
#    response = await post_to_add_account(
#        client,
#        SECOND_USER["name"],
#        SECOND_USER["email"],
#        SECOND_USER["password"]
#    )
#    payload = get_verified_payload(response, "add_account")
#    assert payload['status'] == GQLStatus.SUCCESS.name
#    assert payload['errors'] is None
#    assert payload['result']
#
#@pytest.mark.asyncio(scope="session")
#async def test_verify_second_email_should_succeed(client):
#    token = URLSafeTimedSerializer(SECRET_KEY).dumps(2, salt=VERIFY_TOKEN_SALT)
#    response = await post_to_verify_email(client, token)
#    payload = get_verified_payload(response, "verify_email")
#    assert payload['status'] == GQLStatus.SUCCESS.name
#    assert payload['errors'] is None
#    assert payload['result']
#
#@pytest.mark.asyncio(scope="session")
#async def test_add_second_team_should_succeed(client, token):
#    response = await post_to_add_team(
#        client,
#        token,
#        SECOND_TEAM
#    )
#    payload = get_verified_payload(response, "add_team")
#    assert payload['status'] == GQLStatus.SUCCESS.name
#    assert payload['errors'] is None
#    assert payload['result']
#
#@pytest.mark.asyncio(scope="session")
#async def test_add_child_team_should_succeed(client, token):
#    response = await post_to_add_team(
#        client,
#        token,
#        CHILD_OF_FIRST_TEAM,
#        1
#    )
#    payload = get_verified_payload(response, "add_team")
#    assert payload['status'] == GQLStatus.SUCCESS.name
#    assert payload['errors'] is None
#    assert payload['result']
#








#@pytest.mark.asyncio(scope="session")
#async def test_request_read_should_succeed(client, token):
#    team_id = 1
#    response = await post_to_request_read(
#        client,
#        token,
#        team_id
#    )
#    payload = get_verified_payload(response, "add_team")
#    assert payload['status'] == GQLStatus.SUCCESS.name
#    assert payload['errors'] is None
#    assert payload['result']

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







