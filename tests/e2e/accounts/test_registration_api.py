import pytest
import pytest_asyncio

from src.breedgraph.config import SITE_NAME

from tests.e2e.payload_helpers import get_verified_payload
from tests.e2e.accounts.post_methods import (
    post_to_add_first_account,
    post_to_verify_email,
    post_to_login,
    post_to_add_email,
    post_to_add_account,
    post_to_add_team,
    post_to_remove_team,
    post_to_teams,
    post_to_request_read,
    post_to_accounts,
    post_to_account,
    #post_to_get_affiliations,
    post_to_add_read
)

#from tests.e2e.accounts.gmail_fetching import confirm_email_delivered_to_gmail, get_json_from_gmail
from tests.mailhog_fetching import confirm_email_delivered, get_json_from_email

from src.breedgraph.entrypoints.fastapi.graphql.decorators import GQLStatus
from src.breedgraph.custom_exceptions import TooManyRetries, NoResultFoundError
from src.breedgraph.domain.model.accounts import Access, Authorisation


def assert_payload_success(payload):
    assert payload['status'] == GQLStatus.SUCCESS.name
    assert payload['errors'] is None
    assert payload['result']


async def check_verify_email(client, mailto: str, name: str):
    #json_content = await get_json_from_gmail(mailto=mailto, subject=f"{SITE_NAME} account email verification for {name}")
    json_content = await get_json_from_email(mailto=mailto, subject=f"{SITE_NAME} account email verification")
    token = json_content['token']
    response = await post_to_verify_email(client, token)
    assert_payload_success(get_verified_payload(response, "verify_email"))

@pytest.mark.usefixtures("session_database")
@pytest.mark.asyncio(scope="session")
async def test_first_user_register_verify_login(client, user_input_generator):

    first_user_input = user_input_generator.new_user_input()
    response = await post_to_add_first_account(
        client,
        first_user_input["name"],
        first_user_input["email"],
        first_user_input["password"],
        first_user_input["team_name"]
    )
    assert_payload_success(get_verified_payload(response, "add_first_account"))

    await check_verify_email(client, first_user_input['email'], first_user_input['name'])

    login_response = await post_to_login(
        client,
        first_user_input["name"],
        first_user_input["password"],
    )
    login_payload = get_verified_payload(login_response, "login")
    assert_payload_success(login_payload)


@pytest_asyncio.fixture(scope="session")
async def admin_login_token(client, user_input_generator) -> str:
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
async def test_second_user_invited_registers_and_verifies(client, user_input_generator, admin_login_token):
    # first user invites the second by adding an email address to their allowed list
    second_user_input = user_input_generator.new_user_input()
    invite_response = await post_to_add_email(
        client,
        admin_login_token,
        second_user_input["email"]
    )
    invite_payload = get_verified_payload(invite_response, "add_email")

    assert_payload_success(invite_payload)
    assert await confirm_email_delivered(
        mailto=second_user_input["email"],
        subject=f"{SITE_NAME} registration now available"
    )

    # second user can then register
    register_response = await post_to_add_account(
        client,
        second_user_input["name"],
        second_user_input["email"],
        second_user_input["password"]
    )
    register_payload = get_verified_payload(register_response, "add_account")
    assert_payload_success(register_payload)

    await check_verify_email(client, second_user_input['email'], second_user_input['name'])

@pytest.mark.asyncio(scope="session")
async def test_admin_adds_removes_team(client, user_input_generator, admin_login_token):
    new_team_name = user_input_generator.user_inputs[1]['team_name']
    add_team_response = await post_to_add_team(
        client,
        admin_login_token,
        new_team_name
    )
    add_team_payload = get_verified_payload(add_team_response, "add_team")
    assert_payload_success(add_team_payload)

    teams_request_response = await post_to_teams(
        client,
        admin_login_token
    )
    teams_payload = get_verified_payload(teams_request_response, "teams")
    assert teams_payload['result']

    new_team_id = None
    for team in teams_payload['result']:
        if team['name'] == new_team_name:
            new_team_id = team['id']
            break
    assert new_team_id is not None

    remove_team_response = await post_to_remove_team(
        client,
        admin_login_token,
        new_team_id
    )
    remove_team_payload = get_verified_payload(remove_team_response, "remove_team")
    assert_payload_success(remove_team_payload)


@pytest.mark.asyncio(scope="session")
async def test_admin_adds_child_team(client, user_input_generator, admin_login_token):
    # get existing parent team ID from teams view
    teams_request_response = await post_to_teams(
        client,
        admin_login_token
    )
    teams_payload = get_verified_payload(teams_request_response, "teams")
    assert teams_payload['result']

    parent_team_id = teams_payload['result'][0]['id']  # should only be one team so far, from first user registration

    # Use second user input for team name
    child_team_name = user_input_generator.user_inputs[1]['team_name']
    add_child_team_response = await post_to_add_team(
        client,
        admin_login_token,
        child_team_name,
        parent_team_id
    )
    add_child_team_payload = get_verified_payload(add_child_team_response, "add_team")
    assert_payload_success(add_child_team_payload)

    # make sure this team is now in the view for teams and the parent relationship is properly resolved
    teams_request_response = await post_to_teams(
        client,
        admin_login_token
    )
    teams_payload = get_verified_payload(teams_request_response, "teams")
    assert teams_payload['result']
    for team in teams_payload['result']:
        if team['name'] == child_team_name:
            assert team['parent']['id'] == parent_team_id
            break
    else:
        raise NoResultFoundError("New child team not listed in teams view")
    # Then test fetching team by parent id and navigating to the child
    teams_request_response = await post_to_teams(
        client,
        admin_login_token,
        team_id = parent_team_id
    )
    parent_team_payload = get_verified_payload(teams_request_response, "teams")
    parent_team = parent_team_payload['result'][0]
    assert parent_team['id'] == parent_team_id
    for t in parent_team['children']:
        if t['name'] == child_team_name:
            assert t['parent']['id'] == parent_team_id
            break
    else:
        raise NoResultFoundError("New child team not resolved properly by parent/child relationship")


@pytest_asyncio.fixture(scope="session")
async def second_user_login_token(client, user_input_generator) -> str:
    second_user_input = user_input_generator.user_inputs[1]

    login_response = await post_to_login(
        client,
        second_user_input["name"],
        second_user_input["password"],
    )
    login_payload = get_verified_payload(login_response, "login")
    assert_payload_success(login_payload)
    yield login_payload['result']['access_token']


@pytest.mark.asyncio(scope="session")
async def test_admin_requests_read(client, admin_login_token):
    teams_request_response = await post_to_teams(
        client,
        admin_login_token
    )
    teams_payload = get_verified_payload(teams_request_response, "teams")
    assert teams_payload['result']

    team_id = teams_payload['result'][0]['id']
    read_request_response = await post_to_request_read(
        client,
        admin_login_token,
        team_id
    )
    request_read_payload = get_verified_payload(read_request_response, "request_read")
    assert_payload_success(request_read_payload)


@pytest.mark.asyncio(scope="session")
async def test_non_admin_requests_read_from_root(client, user_input_generator, second_user_login_token):
    admin_user_input = user_input_generator.user_inputs[0]
    second_user_input = user_input_generator.user_inputs[1]

    teams_request_response = await post_to_teams(
        client,
        second_user_login_token
    )
    teams_payload = get_verified_payload(teams_request_response, "teams")
    assert teams_payload['result']
    team_id = teams_payload['result'][0]['id']
    request_read_response = await post_to_request_read(
        client,
        second_user_login_token,
        team_id
    )
    request_read_payload = get_verified_payload(request_read_response, "request_read")
    assert_payload_success(request_read_payload)
    assert await confirm_email_delivered(
        admin_user_input["email"],
        f'{SITE_NAME} read access requested',
        string_in_body = f'{second_user_input["name"]} has requested read access to data written by {admin_user_input["team_name"]}.'
    )

@pytest.mark.asyncio(scope="session")
async def test_admin_adds_read_to_child_team(client, user_input_generator, admin_login_token, second_user_login_token):
    # get ids of requesting accounts from teams
    teams_request_response = await post_to_teams(
        client,
        admin_login_token
    )
    teams_payload = get_verified_payload(teams_request_response, "teams")
    assert teams_payload['result']
    # find request
    requested_team = [t for t in teams_payload['result'] if t['requests']][0]
    assert requested_team['parent'] is None
    requesting_account_id = requested_team['requests'][0]
    child_team = requested_team['children'][0]

    # get the corresponding account to see user details (for admin to identify the user)
    accounts_response = await post_to_accounts(
        client,
        admin_login_token,
        user_id=requesting_account_id
    )
    accounts_payload = get_verified_payload(accounts_response, "accounts")
    requesting_account = accounts_payload['result'][0]
    assert requesting_account

    add_read_response = await post_to_add_read(
        client,
        admin_login_token,
        user=requesting_account_id,
        team=child_team['id']
    )

    add_read_payload = get_verified_payload(add_read_response, "add_read")
    assert_payload_success(add_read_payload)
    assert await confirm_email_delivered(
        requesting_account['user']['email'],
        f'{SITE_NAME} read access added',
        string_in_body=f'Read access to data written by {child_team["name"]} has been added to your account.'
    )

    # confirm the affiliation is now in the admin users accounts as authorised
    updated_account_from_admin_response = await post_to_accounts(
        client,
        admin_login_token,
        user_id=requesting_account_id
    )
    updated_account_from_admin = get_verified_payload(updated_account_from_admin_response, "accounts")['result'][0]
    assert updated_account_from_admin['affiliations'][0]['authorisation'] == Authorisation.AUTHORISED

    # and confirm the affiliation is now in the second users account
    second_user_account_response = await post_to_account(
        client,
        admin_login_token
    )
    second_user_account = get_verified_payload(second_user_account_response, "account")['result'][0]
    assert second_user_account['affiliations'][0]['authorisation'] == Authorisation.AUTHORISED


@pytest.mark.asyncio(scope="session")
async def test_admin_removes_read(client, admin_login_token):
    pass

