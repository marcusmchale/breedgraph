import pytest

from src.breedgraph.config import SITE_NAME

from tests.e2e.utils import get_verified_payload, assert_payload_success
from tests.e2e.accounts.post_methods import (
    post_to_create_account,
    post_to_verify_email,
    post_to_login,
    post_to_add_email,
    post_to_request_affiliation,
    post_to_approve_affiliation
)

from tests.e2e.organisations.post_methods import (
    post_to_create_team,
    post_to_delete_team,
    post_to_team,
    post_to_organisations
)
import logging
#from tests.e2e.accounts.gmail_fetching import confirm_email_delivered_to_gmail, get_json_from_gmail
from tests.utilities.mailhog_fetching import confirm_email_delivered, get_json_from_email

from src.breedgraph.domain.model.controls import Access
from src.breedgraph.custom_exceptions import NoResultFoundError

async def check_verify_email(client, mailto: str, name: str):
    #json_content = await get_json_from_gmail(mailto=mailto, subject=f"{SITE_NAME} account email verification for {name}")
    json_content = await get_json_from_email(mailto=mailto, subject=f"{SITE_NAME} account email verification")
    token = json_content['token']
    response = await post_to_verify_email(client, token)
    assert_payload_success(get_verified_payload(response, "accountsVerifyEmail"))

@pytest.mark.usefixtures("session_database")
@pytest.mark.asyncio(scope="session")
async def test_first_user_register_verify_login(client, user_input_generator):
    first_user_input = user_input_generator.new_user_input()
    response = await post_to_create_account(
        client,
        first_user_input["name"],
        first_user_input["email"],
        first_user_input["password"]
    )
    assert_payload_success(get_verified_payload(response, "accountsCreateAccount"))
    await check_verify_email(client, first_user_input['email'], first_user_input['name'])
    login_response = await post_to_login(
        client,
        first_user_input["name"],
        first_user_input["password"],
    )
    login_payload = get_verified_payload(login_response, "accountsLogin")
    assert_payload_success(login_payload)

@pytest.mark.asyncio(scope="session")
async def test_second_user_invited_registers_and_verifies(client, user_input_generator, first_user_login_token):
    # first user invites the second by adding an email address to their allowed list
    second_user_input = user_input_generator.new_user_input()
    invite_response = await post_to_add_email(
        client,
        first_user_login_token,
        second_user_input["email"]
    )
    logging.debug(f"Using login token {first_user_login_token} to invite {second_user_input['email']}")
    invite_payload = get_verified_payload(invite_response, "accountsAddEmail")
    assert_payload_success(invite_payload)
    assert await confirm_email_delivered(
        mailto=second_user_input["email"],
        subject=f"{SITE_NAME} registration now available"
    )
    # second user can then register
    register_response = await post_to_create_account(
        client,
        second_user_input["name"],
        second_user_input["email"],
        second_user_input["password"]
    )
    register_payload = get_verified_payload(register_response, "accountsCreateAccount")
    assert_payload_success(register_payload)
    await check_verify_email(client, second_user_input['email'], second_user_input['name'])

@pytest.mark.asyncio(scope="session")
async def test_first_user_creates_deletes_team(client, user_input_generator, first_user_login_token):
    new_team_name = user_input_generator.user_inputs[1]['team_name']
    create_team_response = await post_to_create_team(
        client,
        first_user_login_token,
        new_team_name
    )
    create_team_payload = get_verified_payload(create_team_response, "organisationsCreateTeam")
    assert_payload_success(create_team_payload)
    organisations_request_response = await post_to_organisations(
        client,
        first_user_login_token
    )
    organisations_payload = get_verified_payload(organisations_request_response, "organisations")
    organisation_root_ids = [i.get('id') for i in organisations_payload.get('result')]

    delete_team_response = await post_to_delete_team(
        client,
        first_user_login_token,
        team_id= organisation_root_ids[0]
    )
    delete_team_payload = get_verified_payload(delete_team_response, "organisationsDeleteTeam")
    assert_payload_success(delete_team_payload)

    # confirm we can't see the team anymore
    team_request_response = await post_to_team(
        client,
        first_user_login_token,
        team_id= organisation_root_ids[0]
    )
    team_payload = get_verified_payload(team_request_response, "organisationsTeam")
    assert team_payload.get('status') == 'NOT_FOUND'

    organisations_request_response = await post_to_organisations(
        client,
        first_user_login_token
    )
    organisations_payload = get_verified_payload(organisations_request_response, "organisations")
    assert organisations_payload.get('status') == 'NOT_FOUND'
    assert not organisations_payload.get('result')


@pytest.mark.asyncio(scope="session")
async def test_second_user_builds_organisation(client, user_input_generator, second_user_login_token):
    first_team_name = user_input_generator.new_user_input()['team_name']
    await post_to_create_team(client, second_user_login_token, first_team_name)

    organisations_request_response = await post_to_organisations(client,second_user_login_token)
    organisations_payload = get_verified_payload(organisations_request_response, "organisations")
    organisation_root_ids = [i.get('id') for i in organisations_payload.get('result')]

    parent_team_id = organisation_root_ids[0]
    second_team_name = user_input_generator.new_user_input()['team_name']
    add_child_team_response = await post_to_create_team(
        client,
        second_user_login_token,
        second_team_name,
        parent_id = parent_team_id
    )
    create_child_team_payload = get_verified_payload(add_child_team_response, "organisationsCreateTeam")
    assert_payload_success(create_child_team_payload)
    # make sure this team is now part of the organisation
    team_request_response = await post_to_team(
        client,
        second_user_login_token,
        team_id=parent_team_id
    )
    team_payload = get_verified_payload(team_request_response, "organisationsTeam")
    for c in team_payload.get('result').get('children'):
        if c.get('name')== second_team_name:
            break
    else:
        raise NoResultFoundError

@pytest.mark.asyncio(scope="session")
async def test_first_user_requests_read_affiliation(client, user_input_generator, first_user_login_token):
    organisations_request_response = await post_to_organisations(client, first_user_login_token)
    organisations_payload = get_verified_payload(organisations_request_response, "organisations")
    organisation_root_ids = [i.get('id') for i in organisations_payload.get('result')]
    organisation_root_names = [i.get('name') for i in organisations_payload.get('result')]
    team_id = organisation_root_ids[0]
    team_name = organisation_root_names[0]

    affiliation_request_response = await post_to_request_affiliation(
        client,
        first_user_login_token,
        team_id,
        Access.READ
    )
    affiliation_request_payload = get_verified_payload(affiliation_request_response, "accountsRequestAffiliation")
    assert_payload_success(affiliation_request_payload)

    first_user_input = user_input_generator.user_inputs[0]
    second_user_input = user_input_generator.user_inputs[1]
    # the second user should receive an email
    assert await confirm_email_delivered(
        second_user_input["email"],
        f'{SITE_NAME} {Access.READ.name.casefold()} access requested',
        string_in_body=f'{first_user_input["name"]} requested {Access.READ.name.casefold()} access to {team_name}.'
    )

@pytest.mark.asyncio(scope="session")
async def test_second_user_approves_read_affiliation_to_child_team(
        client,
        user_input_generator,
        second_user_login_token
):
    organisations_request_response = await post_to_organisations(client, second_user_login_token)
    organisations_payload = get_verified_payload(organisations_request_response, "organisations")
    request_type = Access.READ
    read_affiliations = organisations_payload.get('result')[0].get('affiliations').get(request_type.casefold())
    requests = [a for a in read_affiliations if a.get('authorisation') == 'REQUESTED']
    assert requests
    request = requests[0]
    first_user_input = user_input_generator.user_inputs[0]
    assert request.get('user').get('name') == first_user_input.get('name')
    request_user_id = request.get('user').get('id')
    child_team_id = organisations_payload.get('result')[0].get('children')[0].get('id')
    child_team_name = organisations_payload.get('result')[0].get('children')[0].get('name')
    approve_read_response = await post_to_approve_affiliation(
        client,
        second_user_login_token,
        user_id=request_user_id,
        team_id=child_team_id,
        access=request_type
    )
    approve_read_payload = get_verified_payload(approve_read_response, "accountsApproveAffiliation")
    assert_payload_success(approve_read_payload)
    first_user_input = user_input_generator.user_inputs[0]
    assert await confirm_email_delivered(
        first_user_input['email'],
        f'{SITE_NAME} read access approved',
        string_in_body=f"Your account was approved for {Access.READ.name.casefold()} access to {child_team_name}."
    )


#@pytest.mark.asyncio(scope="session")
#async def test_second_user_revokes_approved_read(client, user_input_generator, first_user_login_token, second_user_login_token):
#    admin_name = user_input_generator.user_inputs[0]['name']
#    teams_request_response = await post_to_teams(
#        client,
#        first_user_login_token
#    )
#    teams_payload = get_verified_payload(teams_request_response, "teams")
#    assert teams_payload.get('result')
#    for t in teams_payload.get('result'):
#        for u in t.get('readers', []):
#            if u.get('name') != admin_name:
#                remove_response = await post_to_remove_affiliation(
#                    client,
#                    first_user_login_token,
#                    user=u.get('id'),
#                    team=t.get('id'),
#                    access=Access.READ
#                )
#                remove_payload = get_verified_payload(remove_response, "remove_affiliation")
#                assert_payload_success(remove_payload)
#
#                # confirm the affiliation is no longer in the second users account
#                second_user_account_response = await post_to_account(
#                    client,
#                    second_user_login_token
#                )
#                second_user_account = get_verified_payload(second_user_account_response, "account")['result']
#                for tt in second_user_account['reads']:
#                    if t.get('id') == tt['id']:
#                        raise ValueError("Read is still in the users account")
#
#    teams_request_response = await post_to_teams(
#        client,
#        first_user_login_token
#    )
#    teams_payload = get_verified_payload(teams_request_response, "teams")
#    assert teams_payload.get('result')
#    for t in teams_payload.get('result'):
#        for u in t.get('readers', []):
#            if u.get('name') != admin_name:
#                raise ValueError("Other users are still listed as readers")
#
#@pytest.mark.asyncio(scope="session")
#async def test_second_user_changes_details(client, user_input_generator, second_user_login_token):
#    second_user_account_response = await post_to_account(
#        client,
#        second_user_login_token
#    )
#    second_user_account = get_verified_payload(second_user_account_response, "account")['result']
#
#    new_details = user_input_generator.new_user_input()
#    edit_response = await post_to_edit_user(
#        client,
#        token=second_user_login_token,
#        name=new_details['name'],
#        email=new_details['email'],
#        password = new_details['password']
#    )
#    edit_payload = get_verified_payload(edit_response, "edit_user")
#    assert_payload_success(edit_payload)
#
#    changed_user_account_response = await post_to_account(
#        client,
#        second_user_login_token
#    )
#    changed_user_account = get_verified_payload(changed_user_account_response, "account")['result']
#    assert second_user_account != changed_user_account
#    assert changed_user_account
#