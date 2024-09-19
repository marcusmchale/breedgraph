import pytest
import pytest_asyncio

from src.breedgraph.config import SITE_NAME

from tests.e2e.payload_helpers import get_verified_payload
from tests.e2e.accounts.post_methods import (
    post_to_add_account,
    post_to_verify_email,
    post_to_login,
    post_to_add_email,
    post_to_users,
    post_to_edit_user,
    post_to_account,
    post_to_request_affiliation,
    post_to_approve_affiliation,
    post_to_remove_affiliation
)

from tests.e2e.organisations.post_methods import (
    post_to_add_team,
    post_to_remove_team,
    post_to_team,
    post_to_organisations
)

#from tests.e2e.accounts.gmail_fetching import confirm_email_delivered_to_gmail, get_json_from_gmail
from tests.mailhog_fetching import confirm_email_delivered, get_json_from_email

from src.breedgraph.entrypoints.fastapi.graphql.decorators import GQLStatus
from src.breedgraph.custom_exceptions import TooManyRetries, NoResultFoundError

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
    response = await post_to_add_account(
        client,
        first_user_input["name"],
        first_user_input["email"],
        first_user_input["password"]
    )
    assert_payload_success(get_verified_payload(response, "add_account"))
    await check_verify_email(client, first_user_input['email'], first_user_input['name'])

    login_response = await post_to_login(
        client,
        first_user_input["name"],
        first_user_input["password"],
    )
    login_payload = get_verified_payload(login_response, "login")
    assert_payload_success(login_payload)

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
async def test_first_user_adds_removes_team(client, user_input_generator, first_user_login_token):
    new_team_name = user_input_generator.user_inputs[1]['team_name']
    add_team_response = await post_to_add_team(
        client,
        first_user_login_token,
        new_team_name
    )
    add_team_payload = get_verified_payload(add_team_response, "add_team")
    assert_payload_success(add_team_payload)
    organisations_request_response = await post_to_organisations(
        client,
        first_user_login_token
    )
    organisations_payload = get_verified_payload(organisations_request_response, "organisations")
    organisation_root_ids = [i.get('id') for i in organisations_payload.get('result')]

    team_request_response = await post_to_team(
        client,
        first_user_login_token,
        team_id = organisation_root_ids[0]
    )
    team_payload = get_verified_payload(team_request_response, "team")
    assert team_payload.get('result').get('id')

    remove_team_response = await post_to_remove_team(
        client,
        first_user_login_token,
        organisation_root_ids[0]
    )
    remove_team_payload = get_verified_payload(remove_team_response, "remove_team")
    assert_payload_success(remove_team_payload)

    # confirm we can't see the team anymore
    team_request_response = await post_to_team(
        client,
        first_user_login_token,
        team_id = organisation_root_ids[0]
    )
    team_payload = get_verified_payload(team_request_response, "team")
    assert team_payload.get('status') == 'NOT_FOUND'

    organisations_request_response = await post_to_organisations(
        client,
        first_user_login_token
    )
    organisations_payload = get_verified_payload(organisations_request_response, "organisations")
    assert organisations_payload.get('status') == 'NOT_FOUND'
    assert not organisations_payload.get('result')


@pytest.mark.asyncio(scope="session")
async def test_second_user_build_organisation(client, user_input_generator, second_user_login_token):
    first_team_name = user_input_generator.new_user_input()['team_name']
    await post_to_add_team(client, second_user_login_token, first_team_name)

    organisations_request_response = await post_to_organisations(client,second_user_login_token)
    organisations_payload = get_verified_payload(organisations_request_response, "organisations")
    organisation_root_ids = [i.get('id') for i in organisations_payload.get('result')]

    parent_team_id = organisation_root_ids[0]
    second_team_name = user_input_generator.new_user_input()['team_name']
    add_child_team_response = await post_to_add_team(
        client,
        second_user_login_token,
        second_team_name,
        parent_team_id
    )
    add_child_team_payload = get_verified_payload(add_child_team_response, "add_team")
    assert_payload_success(add_child_team_payload)
    # make sure this team is now part of the organisation
    team_request_response = await post_to_team(
        client,
        second_user_login_token,
        team_id=parent_team_id
    )
    team_payload = get_verified_payload(team_request_response, "team")
    for c in team_payload.get('result').get('children'):
        if c.get('name')== second_team_name:
            break
    else:
        raise NoResultFoundError


@pytest.mark.asyncio(scope="session")
async def test_first_user_requests_affiliation(client, first_user_login_token):
    organisations_request_response = await post_to_organisations(client, first_user_login_token)

    import pdb; pdb.set_trace()

    organisations_payload = get_verified_payload(organisations_request_response, "organisations")
    import pdb;
    pdb.set_trace()
    organisation_root_ids = [i.get('id') for i in organisations_payload.get('result')]
    import pdb; pdb.set_trace()


    teams_request_response = await post_to_teams(
        client,
        first_user_login_token
    )
    teams_payload = get_verified_payload(teams_request_response, "teams")
    assert teams_payload['result']

    team_id = teams_payload['result'][0]['id']
    affiliation_request_response = await post_to_request_affiliation(
        client,
        first_user_login_token,
        team_id,
        Access.READ
    )
    affiliation_request_payload = get_verified_payload(affiliation_request_response, "request_affiliation")
    assert_payload_success(affiliation_request_payload)

    account_response = await post_to_account(
        client,
        first_user_login_token
    )
    user_account = get_verified_payload(account_response, "account")['result']
    for t in user_account['reads']:
        if t['id'] == team_id:
            break
    else:
        raise NoResultFoundError("Couldn't find the approved read in the admin account")


@pytest.mark.asyncio(scope="session")
async def test_non_admin_requests_read_from_root_then_approved_for_child(
        client,
        user_input_generator,
        first_user_login_token,
        second_user_login_token
):
    admin_user_input = user_input_generator.user_inputs[0]
    second_user_input = user_input_generator.user_inputs[1]
    teams_request_response = await post_to_teams(
        client,
        second_user_login_token
    )
    teams_payload = get_verified_payload(teams_request_response, "teams")
    assert teams_payload['result']
    team_id = teams_payload['result'][0]['id']
    request_affiliation_response = await post_to_request_affiliation(
        client,
        second_user_login_token,
        team_id,
        access=Access.READ
    )
    request_affiliation_payload = get_verified_payload(request_affiliation_response, "request_affiliation")
    assert_payload_success(request_affiliation_payload)
    # the admin should receive an email
    assert await confirm_email_delivered(
        admin_user_input["email"],
        f'{SITE_NAME} {Access.READ.name.casefold()} access requested',
        string_in_body = f'{second_user_input["name"]} requested {Access.READ.name.casefold()} access to {admin_user_input["team_name"]}.'
    )
    # admin gets id of requesting account
    teams_request_response = await post_to_teams(
        client,
        first_user_login_token
    )
    teams_payload = get_verified_payload(teams_request_response, "teams")
    assert teams_payload['result']
    # find a child team with the inherited request
    child_requests = [t for t in teams_payload['result'] if t['read_requests'] and t['parent']]
    try:
        assert len(child_requests) == 1
    except AssertionError:
        raise AssertionError("The team layout request is not as expected from this set of tests - consider earlier tests may have failed")

    child_team = child_requests[0]
    try:
        assert len(child_team['read_requests']) == 1
    except AssertionError:
        raise AssertionError("The request layout is not as expected from this set of tests - consider earlier tests may have failed")

    for user in child_team['read_requests']:
        approve_read_response = await post_to_approve_affiliation(
            client,
            first_user_login_token,
            user=user['id'],
            team=child_team['id'],
            access=Access.READ
        )
        approve_read_payload = get_verified_payload(approve_read_response, "approve_affiliation")
        assert_payload_success(approve_read_payload)
        assert await confirm_email_delivered(
            user['email'],
            f'{SITE_NAME} read access approved',
            string_in_body=f"Your account was approved for {Access.READ.name.casefold()} access to {child_team['fullname']}."
        )
    # confirm the affiliation is now in the second users account
    second_user_account_response = await post_to_account(
        client,
        second_user_login_token
    )
    second_user_account = get_verified_payload(second_user_account_response, "account")['result']

    for t in second_user_account['reads']:
        if t['id'] == child_team['id']:
            break
    else:
        raise NoResultFoundError("Couldn't find the approved read in the users account")

@pytest.mark.asyncio(scope="session")
async def test_admin_removes_approved_read(client, user_input_generator, first_user_login_token, second_user_login_token):
    admin_name = user_input_generator.user_inputs[0]['name']
    teams_request_response = await post_to_teams(
        client,
        first_user_login_token
    )
    teams_payload = get_verified_payload(teams_request_response, "teams")
    assert teams_payload.get('result')
    for t in teams_payload.get('result'):
        for u in t.get('readers', []):
            if u.get('name') != admin_name:
                remove_response = await post_to_remove_affiliation(
                    client,
                    first_user_login_token,
                    user=u.get('id'),
                    team=t.get('id'),
                    access=Access.READ
                )
                remove_payload = get_verified_payload(remove_response, "remove_affiliation")
                assert_payload_success(remove_payload)

                # confirm the affiliation is no longer in the second users account
                second_user_account_response = await post_to_account(
                    client,
                    second_user_login_token
                )
                second_user_account = get_verified_payload(second_user_account_response, "account")['result']
                for tt in second_user_account['reads']:
                    if t.get('id') == tt['id']:
                        raise ValueError("Read is still in the users account")

    teams_request_response = await post_to_teams(
        client,
        first_user_login_token
    )
    teams_payload = get_verified_payload(teams_request_response, "teams")
    assert teams_payload.get('result')
    for t in teams_payload.get('result'):
        for u in t.get('readers', []):
            if u.get('name') != admin_name:
                raise ValueError("Other users are still listed as readers")

@pytest.mark.asyncio(scope="session")
async def test_second_user_changes_details(client, user_input_generator, second_user_login_token):
    second_user_account_response = await post_to_account(
        client,
        second_user_login_token
    )
    second_user_account = get_verified_payload(second_user_account_response, "account")['result']

    new_details = user_input_generator.new_user_input()
    edit_response = await post_to_edit_user(
        client,
        token=second_user_login_token,
        name=new_details['name'],
        email=new_details['email'],
        password = new_details['password']
    )
    edit_payload = get_verified_payload(edit_response, "edit_user")
    assert_payload_success(edit_payload)

    changed_user_account_response = await post_to_account(
        client,
        second_user_login_token
    )
    changed_user_account = get_verified_payload(changed_user_account_response, "account")['result']
    assert second_user_account != changed_user_account
    assert changed_user_account
