import pytest

from breedgraph.custom_exceptions import NoResultFoundError
from tests.breedgraph.e2e.teams.post_methods import (
    post_to_create_team,
    post_to_teams_roots,
    post_to_team
)

from tests.breedgraph.e2e.utils import get_verified_payload, assert_payload_success
from tests.breedgraph.scenarios import TeamTreeBuilder


@pytest.mark.asyncio(loop_scope="session")
async def test_create_and_get(
        team_tree_build_context,
        login_token_factory,
        client
):
    user_id = team_tree_build_context['user_id']
    login_token = login_token_factory(user_id=user_id)
    team_input = TeamTreeBuilder.team_input()
    response = await post_to_create_team(client=client, token=login_token, team=team_input.model_dump())
    assert_payload_success(get_verified_payload(response, "teamsCreateTeam"))

    team_trees_response = await post_to_teams_roots(client, login_token)
    team_trees_payload = get_verified_payload(team_trees_response, query_name="teamsRoots")
    for team in team_trees_payload.get('result'):
        if team.get('name') == team_input.name:
            team_id = team.get('id')
            break
    else:
        raise NoResultFoundError("Couldn't find new team at team trees endpoint")

    team_response = await post_to_team(client=client, token=login_token, team_id=team_id)
    team_payload = get_verified_payload(team_response, "teamsTeam")
    assert team_payload.get('result').get('name') == team_input.name

#@pytest.mark.asyncio(loop_scope="session")
#async def test_rename_team(
#        team_tree_build_context,
#        login_token_factory,
#        client
#):
#    user_id = team_tree_build_context['user_id']
#    login_token = login_token_factory(user_id=user_id)
#    team_trees_response = await post_to_teams_roots(client, login_token)
#    team_trees_payload = get_verified_payload(team_trees_response, query_name="teamsRoots")
#    team_id = team_trees_payload.get('result')[0].get('id')
#    new_input = TeamTreeBuilder.team_input()
#    new_team_input = {
#        'teamId': team_id,
#        'name': new_input.name
#    }
#    teams_edit_response = await post_to_update_team(
#        client,
#        login_token,
#        team=new_team_input
#    )
#    teams_edit_payload = get_verified_payload(teams_edit_response, "teamsUpdateTeam")
#    assert_payload_success(teams_edit_payload)
#
#    team_request_response = await post_to_team(
#        client,
#        login_token,
#        team_id=team_id
#    )
#    team_payload = get_verified_payload(team_request_response, "teamsTeam")
#    renamed_team = team_payload['result']
#    assert renamed_team['name'] == new_input.name
#
#
