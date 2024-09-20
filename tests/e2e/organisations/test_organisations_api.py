import pytest

from tests.e2e.organisations.post_methods import (
    post_to_organisations,
    post_to_edit_team,
    post_to_team
)

from tests.e2e.payload_helpers import get_verified_payload


@pytest.mark.asyncio(scope="session")
async def test_second_user_renames_team(client, user_input_generator, second_user_login_token):
    organisations_request_response = await post_to_organisations(client, second_user_login_token)
    organisations_payload = get_verified_payload(organisations_request_response, "organisations")
    organisation_root_ids = [i.get('id') for i in organisations_payload.get('result')]
    organisation_root_names = [i.get('name') for i in organisations_payload.get('result')]
    team_id = organisation_root_ids[0]
    team_name = organisation_root_names[0]

    new_input = user_input_generator.new_user_input()
    teams_edit_response = await post_to_edit_team(
        client,
        second_user_login_token,
        team=team_id,
        name=new_input['team_name'],
        fullname=new_input['team_name']
    )
    teams_edit_payload = get_verified_payload(teams_edit_response, "edit_team")
    assert teams_edit_payload['result']

    team_request_response = await post_to_team(
        client,
        second_user_login_token,
        team_id=team_id
    )
    team_payload = get_verified_payload(team_request_response, "team")
    renamed_team = team_payload['result']
    assert renamed_team['name'] == new_input['team_name']


