import pytest

from tests.e2e.organisations.post_methods import (
    post_to_teams,
    post_to_add_team,
    post_to_remove_team,
    post_to_edit_team
)

from tests.e2e.payload_helpers import get_verified_payload

from src.breedgraph.domain.model.organisations import Authorisation


@pytest.mark.asyncio(scope="session")
async def test_admin_renames_team(client, user_input_generator, admin_login_token):
    teams_request_response = await post_to_teams(
        client,
        admin_login_token,
        team_id=1
    )
    teams_payload = get_verified_payload(teams_request_response, "teams")
    team = teams_payload['result'][0]

    new_input = user_input_generator.new_user_input()
    teams_edit_response = await post_to_edit_team(
        client,
        admin_login_token,
        team=team['id'],
        name=new_input['team_name'],
        fullname=new_input['team_name']
    )
    teams_edit_payload = get_verified_payload(teams_edit_response, "edit_team")
    assert teams_edit_payload['result']

    teams_request_response = await post_to_teams(
        client,
        admin_login_token,
        team_id=1
    )
    teams_payload = get_verified_payload(teams_request_response, "teams")
    renamed_team = teams_payload['result'][0]
    assert renamed_team['name'] == new_input['team_name']


