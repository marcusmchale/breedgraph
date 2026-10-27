import pytest

from breedgraph.config import SITE_NAME
from tests.breedgraph.e2e.utils import get_verified_payload, assert_payload_success
from tests.breedgraph.e2e.accounts.post_methods import (
    post_to_create_account,
    post_to_verify_email,
    post_to_login,
    post_to_invite,
    post_to_request_affiliation,
    post_to_approve_affiliation,
    post_to_remove_heritability
)

from tests.breedgraph.e2e.teams.post_methods import (
    post_to_create_team,
    post_to_delete_team,
    post_to_team,
    post_to_teams_roots
)
#from tests.e2e.accounts.gmail_fetching import confirm_email_delivered_to_gmail, get_json_from_gmail
from tests.breedgraph.utilities.mailhog_fetching import confirm_email_delivered, get_json_from_email

from breedgraph import config
from breedgraph.domain.model import Access
from breedgraph.custom_exceptions import NoResultFoundError
from breedgraph.service_layer.application.terms_of_use import load_legal_text

from tests.breedgraph.e2e.accounts.test_first_account import script as first_account_script

async def check_verify_email(client, mailto: str, name: str):
    #json_content = await get_json_from_gmail(mailto=mailto, subject=f"{SITE_NAME} account email verification for {name}")
    json_content = await get_json_from_email(mailto=mailto, subject=f"{SITE_NAME} account email verification")
    token = json_content['token']
    response = await post_to_verify_email(client, token)
    assert_payload_success(get_verified_payload(response, "accountsVerifyEmail"))

@pytest.mark.asyncio(loop_scope="session")
async def test_first_user_made_on_the_server_logs_in(
        user_registration_context,
        client,
        uow_factory,
        user_input_generator
):
    # the first account is made by scripts/create_first_account.py, as registering needs an invitation
    first_user_input = user_input_generator.new_user_input()
    await first_account_script.create_first_account(
        uow_factory,
        first_user_input["name"],
        first_user_input["email"],
        first_user_input["password_hash"],
        load_legal_text(config.PRIVACY_NOTICE_PATH).content_hash
    )
    login_response = await post_to_login(
        client,
        first_user_input["name"],
        first_user_input["password"],
    )
    login_payload = get_verified_payload(login_response, "accountsLogin")
    assert_payload_success(login_payload)


@pytest.mark.asyncio(loop_scope="session")
async def test_second_user_invited_registers_and_verifies(
        user_registration_context,
        client,
        user_input_generator
):
    # first user invites the second
    second_user_input = user_input_generator.new_user_input()
    invite_response = await post_to_invite(
        client,
        user_registration_context['login_token_user_1'],
        second_user_input["email"]
    )
    invite_payload = get_verified_payload(invite_response, "accountsInvite")
    assert_payload_success(invite_payload)
    invitation = await get_json_from_email(
        mailto=second_user_input["email"],
        subject=f"Invitation to register with {SITE_NAME}"
    )
    # second user can then register with the token from the invitation
    register_response = await post_to_create_account(
        client,
        second_user_input["name"],
        second_user_input["email"],
        second_user_input["password"],
        invitation_token=invitation['token']
    )
    register_payload = get_verified_payload(register_response, "accountsCreateAccount")
    assert_payload_success(register_payload)
    await check_verify_email(client, second_user_input['email'], second_user_input['name'])

@pytest.mark.asyncio(loop_scope="session")
async def test_first_user_creates_deletes_team(
        user_registration_context,
        client,
        user_input_generator
):
    new_team_name = user_input_generator.user_inputs[0]['team_name']
    create_team_response = await post_to_create_team(
        client,
        user_registration_context['login_token_user_1'],
        team = { "name": new_team_name }
    )
    create_team_payload = get_verified_payload(create_team_response, "teamsCreateTeam")
    assert_payload_success(create_team_payload)
    team_trees_request_response = await post_to_teams_roots(
        client,
        user_registration_context['login_token_user_1']
    )
    team_trees_payload = get_verified_payload(team_trees_request_response, "teamsRoots")
    team_tree_root_ids = [i.get('id') for i in team_trees_payload.get('result')]

    delete_team_response = await post_to_delete_team(
        client,
        user_registration_context['login_token_user_1'],
        team_id= team_tree_root_ids[0]
    )
    delete_team_payload = get_verified_payload(delete_team_response, "teamsDeleteTeam")
    assert_payload_success(delete_team_payload)

    # confirm we can't see the team anymore
    team_request_response = await post_to_team(
        client,
        user_registration_context['login_token_user_1'],
        team_id= team_tree_root_ids[0]
    )
    team_payload = get_verified_payload(team_request_response, "teamsTeam")
    assert team_payload.get('result') is None

    team_trees_request_response = await post_to_teams_roots(
        client,
        user_registration_context['login_token_user_1']
    )
    team_trees_payload = get_verified_payload(team_trees_request_response, "teamsRoots")
    assert not team_trees_payload.get('result')

@pytest.mark.asyncio(loop_scope="session")
async def test_second_user_builds_team_tree(
        user_registration_context,
        client,
        user_input_generator
):
    first_team_name = user_input_generator.user_inputs[0]['team_name']
    await post_to_create_team(client, user_registration_context['login_token_user_2'], { "name": first_team_name })

    team_trees_request_response = await post_to_teams_roots(client,user_registration_context['login_token_user_2'])
    team_trees_payload = get_verified_payload(team_trees_request_response, "teamsRoots")
    team_tree_root_ids = [i.get('id') for i in team_trees_payload.get('result')]

    parent_team_id = team_tree_root_ids[0]
    second_team_name = user_input_generator.user_inputs[1]['team_name']
    add_child_team_response = await post_to_create_team(
        client,
        user_registration_context['login_token_user_2'],
        { "name": second_team_name, "parentId": parent_team_id}
    )
    create_child_team_payload = get_verified_payload(add_child_team_response, "teamsCreateTeam")
    assert_payload_success(create_child_team_payload)
    # make sure this team is now part of the team tree
    team_request_response = await post_to_team(
        client,
        user_registration_context['login_token_user_2'],
        team_id=parent_team_id
    )
    team_payload = get_verified_payload(team_request_response, "teamsTeam")
    for c in team_payload.get('result').get('children'):
        if c.get('name')== second_team_name:
            break
    else:
        raise NoResultFoundError

@pytest.mark.asyncio(loop_scope="session")
async def test_first_user_requests_read_affiliation(
        user_registration_context,
        login_token_factory,
        client,
        user_input_generator
):
    team_trees_request_response = await post_to_teams_roots(client, user_registration_context['login_token_user_1'])
    team_trees_payload = get_verified_payload(team_trees_request_response, "teamsRoots")
    team_tree_root_ids = [i.get('id') for i in team_trees_payload.get('result')]
    team_tree_root_names = [i.get('name') for i in team_trees_payload.get('result')]
    team_id = team_tree_root_ids[0]
    team_name = team_tree_root_names[0]

    affiliation_request_response = await post_to_request_affiliation(
        client,
        user_registration_context['login_token_user_1'],
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
        string_in_body=(
            f'{first_user_input["name"]} requested {Access.READ.name.casefold()} access to {team_name} '
            f'and the teams below it.'
        )
    )

@pytest.mark.asyncio(loop_scope="session")
async def test_second_user_approves_read_affiliation_to_child_team(
        user_registration_context,
        client,
        user_input_generator
):
    team_trees_request_response = await post_to_teams_roots(client, user_registration_context['login_token_user_2'])
    team_trees_payload = get_verified_payload(team_trees_request_response, "teamsRoots")
    request_type = Access.READ
    read_affiliations = team_trees_payload.get('result')[0].get('affiliations').get(request_type.casefold())
    requests = [a for a in read_affiliations if a.get('authorisation') == 'REQUESTED']
    assert requests
    request = requests[0]
    first_user_input = user_input_generator.user_inputs[0]
    assert request.get('user').get('name') == first_user_input.get('name')
    request_user_id = request.get('user').get('id')
    child_team_id = team_trees_payload.get('result')[0].get('children')[0].get('id')
    child_team_name = team_trees_payload.get('result')[0].get('children')[0].get('name')
    approve_read_response = await post_to_approve_affiliation(
        client,
        user_registration_context['login_token_user_2'],
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

def child_read_affiliation(roots_payload: dict, user_id: str) -> dict:
    """The user's read affiliation to the first child team, from the second user's view of the team trees"""
    child = roots_payload.get('result')[0].get('children')[0]
    return next(a for a in child.get('directAffiliations').get('read') if a.get('user').get('id') == user_id)

@pytest.mark.asyncio(loop_scope="session")
async def test_first_user_asks_for_read_access_to_the_teams_below_the_child_team(
        user_registration_context,
        client,
        user_input_generator
):
    roots_payload = get_verified_payload(
        await post_to_teams_roots(client, user_registration_context['login_token_user_2']), "teamsRoots"
    )
    child = roots_payload.get('result')[0].get('children')[0]
    first_user_input = user_input_generator.user_inputs[0]
    first_user_id = next(
        a.get('user').get('id') for a in child.get('directAffiliations').get('read')
        if a.get('user').get('name') == first_user_input.get('name')
    )
    user_registration_context['first_user_id'] = first_user_id

    request_payload = get_verified_payload(
        await post_to_request_affiliation(
            client, user_registration_context['login_token_user_1'], child.get('id'), Access.READ, heritable=True
        ),
        "accountsRequestAffiliation"
    )
    assert_payload_success(request_payload)
    # the read access to the child team is kept while the admins decide
    roots_payload = get_verified_payload(
        await post_to_teams_roots(client, user_registration_context['login_token_user_2']), "teamsRoots"
    )
    affiliation = child_read_affiliation(roots_payload, first_user_id)
    assert (affiliation['authorisation'], affiliation['heritable'], affiliation['heritableRequested']) == (
        'AUTHORISED', False, True
    )
    second_user_input = user_input_generator.user_inputs[1]
    assert await confirm_email_delivered(
        second_user_input["email"],
        f'{SITE_NAME} read access requested',
        string_in_body=(
            f'{first_user_input["name"]}, who has read access to {child.get("name")}, '
            f'requested it for the teams below it too.'
        )
    )

@pytest.mark.asyncio(loop_scope="session")
async def test_second_user_approves_read_access_to_the_teams_below_the_child_team(
        user_registration_context,
        client,
        user_input_generator
):
    token = user_registration_context['login_token_user_2']
    first_user_id = user_registration_context['first_user_id']
    child = get_verified_payload(await post_to_teams_roots(client, token), "teamsRoots").get('result')[0].get('children')[0]
    approve_payload = get_verified_payload(
        await post_to_approve_affiliation(
            client, token, user_id=first_user_id, team_id=child.get('id'), access=Access.READ, heritable=True
        ),
        "accountsApproveAffiliation"
    )
    assert_payload_success(approve_payload)
    roots_payload = get_verified_payload(await post_to_teams_roots(client, token), "teamsRoots")
    affiliation = child_read_affiliation(roots_payload, first_user_id)
    assert (affiliation['heritable'], affiliation['heritableRequested']) == (True, False)
    assert await confirm_email_delivered(
        user_input_generator.user_inputs[0]['email'],
        f'{SITE_NAME} read access approved',
        string_in_body=f"Your account was approved for read access to {child.get('name')} and the teams below it."
    )

@pytest.mark.asyncio(loop_scope="session")
async def test_first_user_limits_read_access_to_the_child_team(
        user_registration_context,
        client
):
    token = user_registration_context['login_token_user_2']
    child = get_verified_payload(await post_to_teams_roots(client, token), "teamsRoots").get('result')[0].get('children')[0]
    remove_payload = get_verified_payload(
        await post_to_remove_heritability(
            client, user_registration_context['login_token_user_1'], child.get('id'), Access.READ
        ),
        "accountsRemoveHeritability"
    )
    assert_payload_success(remove_payload)
    roots_payload = get_verified_payload(await post_to_teams_roots(client, token), "teamsRoots")
    affiliation = child_read_affiliation(roots_payload, user_registration_context['first_user_id'])
    assert (affiliation['authorisation'], affiliation['heritable'], affiliation['heritableRequested']) == (
        'AUTHORISED', False, False
    )
