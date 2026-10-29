"""
Team attributions through GraphQL: set on create and update, cleared by null or an empty string, inherited from the
nearest team above with one (Team.inheritedAttribution), and given for an entity controlled by several teams as one
attribution for each, without repeats (controlsAttributions).
"""
import pytest

from breedgraph.domain.model.controls import Access, ReadRelease, ControlledModelLabel
from breedgraph.domain.model.references import LegalReferenceInput
from breedgraph.entrypoints.fastapi.graphql.decorators import GQLStatus

from tests.breedgraph.e2e.teams.post_methods import post_to_create_team, post_to_update_team
from tests.breedgraph.e2e.controls.post_methods import post_to_offer_transfer
from tests.breedgraph.e2e.utils import post_as, get_verified_payload, assert_payload_success
from tests.breedgraph.scenarios import TeamTreeBuilder

TEAMS = "query { teamsRoots { status result { id name attribution inheritedAttribution children { id name attribution inheritedAttribution } } errors { message } } }"
ATTRIBUTIONS = (
    "query ($label: ControlledModelLabel!, $ids: [ID!]!) { "
    " controlsAttributions(entityLabel: $label, entityIds: $ids) { status result { entityId attributions } errors { message } } "
    "}"
)


async def _roots(client, login_token_factory, user_id) -> dict[str, dict]:
    payload = get_verified_payload(await post_as(client, login_token_factory, user_id, TEAMS), 'teamsRoots')
    assert payload['status'] == GQLStatus.SUCCESS.name, payload['errors']
    return {root['name']: root for root in payload['result']}


async def _create(client, token, team: dict):
    assert_payload_success(get_verified_payload(await post_to_create_team(client, token, team), 'teamsCreateTeam'))


async def _update(client, token, team: dict):
    assert_payload_success(get_verified_payload(await post_to_update_team(client, token, team), 'teamsUpdateTeam'))


@pytest.mark.asyncio(loop_scope="session")
async def test_set_cleared_and_inherited(team_tree_build_context, login_token_factory, client):
    user_id = team_tree_build_context['user_id']
    token = login_token_factory(user_id=user_id)
    institute = TeamTreeBuilder.team_input().name
    await _create(client, token, {'name': institute, 'attribution': 'Example Institute'})
    root = (await _roots(client, login_token_factory, user_id))[institute]
    assert (root['attribution'], root['inheritedAttribution']) == ('Example Institute', None)

    group = TeamTreeBuilder.team_input().name
    await _create(client, token, {'name': group, 'parentId': root['id']})
    (child,) = (await _roots(client, login_token_factory, user_id))[institute]['children']
    assert (child['name'], child['attribution'], child['inheritedAttribution']) == (group, None, 'Example Institute')

    # its own, then left alone by an update that doesn't give it, then cleared
    await _update(client, token, {'id': child['id'], 'attribution': 'Wheat Group, Example Institute'})
    (child,) = (await _roots(client, login_token_factory, user_id))[institute]['children']
    assert child['attribution'] == 'Wheat Group, Example Institute'
    await _update(client, token, {'id': child['id'], 'fullname': 'Wheat group'})
    (child,) = (await _roots(client, login_token_factory, user_id))[institute]['children']
    assert child['attribution'] == 'Wheat Group, Example Institute'
    await _update(client, token, {'id': child['id'], 'attribution': '  '})
    (child,) = (await _roots(client, login_token_factory, user_id))[institute]['children']
    assert child['attribution'] is None
    await _update(client, token, {'id': root['id'], 'attribution': None})
    (child,) = (await _roots(client, login_token_factory, user_id))[institute]['children']
    assert child['inheritedAttribution'] is None


@pytest.mark.asyncio(loop_scope="session")
async def test_an_entity_of_several_teams_credits_each(team_tree_build_context, login_token_factory, client, uow_factory):
    user_id = team_tree_build_context['user_id']
    token = login_token_factory(user_id=user_id)
    names = {key: TeamTreeBuilder.team_input().name for key in ('institute', 'lab', 'coop', 'unnamed')}
    await _create(client, token, {'name': names['institute'], 'attribution': 'Example Institute'})
    await _create(client, token, {'name': names['coop'], 'attribution': 'Example Cooperative'})
    await _create(client, token, {'name': names['unnamed']})
    roots = await _roots(client, login_token_factory, user_id)
    await _create(client, token, {'name': names['lab'], 'parentId': roots[names['institute']]['id']})
    roots = await _roots(client, login_token_factory, user_id)
    (lab,) = roots[names['institute']]['children']
    teams = {'institute': int(roots[names['institute']]['id']), 'lab': int(lab['id']),
             'coop': int(roots[names['coop']]['id']), 'unnamed': int(roots[names['unnamed']]['id'])}

    await TeamTreeBuilder(uow_factory=uow_factory).authorise_access(user_id=user_id, team_id=teams['lab'], access=Access.WRITE)
    async with uow_factory.get_uow(user_id=user_id, write_team=teams['lab'], release=ReadRelease.PUBLIC) as uow:
        reference = await uow.repositories.references.create(LegalReferenceInput(description='Shared', text='Terms'))
        await uow.commit()
    # shared with the other teams, each accepting at once as the user is an admin of each
    for team in ('institute', 'coop', 'unnamed'):
        assert_payload_success(get_verified_payload(await post_to_offer_transfer(client, token, {
            'entities': [{'label': ControlledModelLabel.REFERENCE.name, 'id': reference.id}],
            'fromTeamIds': [teams['lab']], 'recipientTeamId': teams[team], 'keepFromTeams': True,
            'toTeamIds': [teams[team]], 'release': ReadRelease.PUBLIC.name
        }), 'controlsOfferTransfer'))

    # in the order of the teams' ids, so as created: the institute's once, though the lab inherits it too, then the
    # cooperative's; none for the unnamed team
    payload = get_verified_payload(
        await post_as(client, login_token_factory, None, ATTRIBUTIONS,
                      {'label': ControlledModelLabel.REFERENCE.name, 'ids': [reference.id]}),
        'controlsAttributions'
    )
    assert payload['status'] == GQLStatus.SUCCESS.name, payload['errors']
    assert payload['result'][0]['attributions'] == ['Example Institute', 'Example Cooperative']
