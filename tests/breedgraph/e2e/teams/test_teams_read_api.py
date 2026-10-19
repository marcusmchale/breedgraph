"""
Team trees and accounts under the read policy (docs/read-access.md, rules 7 and 9), through GraphQL, on the
read-policy scenario: team tree "root" with a child team "child", and a second team tree "other".

- Teams are for signed-in users: anonymous users see none, so the organisations using BreedGraph are not listed
  publicly. A team tree's root is visible to every signed-in user. Its other teams are visible only to their
  affiliates; asked for by id, a hidden team is a placeholder.
- A team's affiliations are shown in full to its admins, and otherwise only the viewer's own.
- Accounts are shown to their owner and to admins of their teams: an affiliation's user. accountsAccount and
  accountsUserAccess need an account.
"""
import pytest

from breedgraph.domain.model.controls import Access
from breedgraph.entrypoints.fastapi.graphql.decorators import GQLStatus

from tests.breedgraph.e2e.utils import post_as, get_verified_payload
from tests.breedgraph.scenarios.read_policy_scenario import VIEWERS, AFFILIATIONS

REDACTED = 'REDACTED'
TEAMS = ('root', 'child', 'other')
ROOTS = ('root', 'other')
PARENTS = {'child': 'root'}

AFFILIATION_FIELDS = "user { id } authorisation heritable"
TEAM_FIELDS = (
    "id name parent { id } children { id } "
    f"affiliations {{ read {{ {AFFILIATION_FIELDS} }} write {{ {AFFILIATION_FIELDS} }} "
    f"admin {{ {AFFILIATION_FIELDS} }} curate {{ {AFFILIATION_FIELDS} }} }}"
)


async def payload_of(client, login_token_factory, read_policy, viewer: str, operation: str, text: str, variables=None):
    response = await post_as(client, login_token_factory, read_policy.user(viewer), text, variables)
    return get_verified_payload(response, operation)


async def result_of(client, login_token_factory, read_policy, viewer: str, operation: str, text: str, variables=None):
    payload = await payload_of(client, login_token_factory, read_policy, viewer, operation, text, variables)
    assert payload['status'] == GQLStatus.SUCCESS.name, payload['errors']
    assert payload['errors'] is None
    return payload['result']


def visible(viewer: str, team: str) -> bool:
    return team in ROOTS or team in AFFILIATIONS.get(viewer, {})


def expected_affiliations(viewer: str, team: str) -> dict[str, set[str]]:
    """{access: users affiliated} as the viewer sees a team: all of them for its admins, else their own"""
    affiliates = {user: accesses.get(team, set()) for user, accesses in AFFILIATIONS.items()}
    is_admin = Access.ADMIN in AFFILIATIONS.get(viewer, {}).get(team, set())
    return {
        access.name.lower(): {user for user, accesses in affiliates.items() if access in accesses and (is_admin or user == viewer)}
        for access in Access
    }


def assert_team(read_policy, viewer: str, name: str, team: dict):
    names = {read_policy[user]: user for user in AFFILIATIONS}
    assert int(team['id']) == read_policy[name]
    assert team['name'] != REDACTED
    assert (int(team['parent']['id']) if team['parent'] else None) == (read_policy[PARENTS[name]] if name in PARENTS else None)
    children = {int(child['id']) for child in team['children'] or []}
    assert children == {read_policy[child] for child, parent in PARENTS.items() if parent == name and visible(viewer, child)}, \
        f"{viewer}: children of {name}"
    affiliations = {
        access: {names[int(affiliation['user']['id'])] for affiliation in team['affiliations'][access] or []}
        for access in ('read', 'write', 'admin', 'curate')
    }
    assert affiliations == expected_affiliations(viewer, name), f"{viewer}: affiliations of {name}"


async def assert_refused_anonymously(client, login_token_factory, read_policy, operation: str, text: str, variables=None):
    payload = await payload_of(client, login_token_factory, read_policy, 'anonymous', operation, text, variables)
    assert payload['status'] != GQLStatus.SUCCESS.name
    assert payload['result'] is None


@pytest.mark.asyncio(loop_scope="session")
@pytest.mark.parametrize('viewer', VIEWERS)
async def test_team_trees(client, login_token_factory, read_policy, viewer):
    query = f"query {{ teamsRoots {{ status result {{ {TEAM_FIELDS} }} errors {{ name message }} }} }}"
    if viewer == 'anonymous':
        await assert_refused_anonymously(client, login_token_factory, read_policy, 'teamsRoots', query)
        return
    result = await result_of(client, login_token_factory, read_policy, viewer, 'teamsRoots', query)
    roots = {int(team['id']): team for team in result}
    # every team tree's root, the scenario's among them
    assert {read_policy[name] for name in ROOTS} <= set(roots)
    for name in ROOTS:
        assert_team(read_policy, viewer, name, roots[read_policy[name]])


@pytest.mark.asyncio(loop_scope="session")
@pytest.mark.parametrize('viewer', VIEWERS)
async def test_teams_by_id(client, login_token_factory, read_policy, viewer):
    by_ids = f"query ($ids: [ID!]) {{ teamsTeams(ids: $ids) {{ status result {{ {TEAM_FIELDS} }} errors {{ name message }} }} }}"
    by_id = "query ($id: ID!) { teamsTeam(id: $id) { status result { id name } errors { name message } } }"
    if viewer == 'anonymous':
        await assert_refused_anonymously(
            client, login_token_factory, read_policy, 'teamsTeams', by_ids, {'ids': [read_policy[name] for name in TEAMS]}
        )
        await assert_refused_anonymously(client, login_token_factory, read_policy, 'teamsTeam', by_id, {'id': read_policy['root']})
        return
    result = await result_of(
        client, login_token_factory, read_policy, viewer, 'teamsTeams', by_ids, {'ids': [read_policy[name] for name in TEAMS]}
    )
    teams = {int(team['id']): team for team in result}
    assert set(teams) == {read_policy[name] for name in TEAMS}
    for name in TEAMS:
        team = teams[read_policy[name]]
        if visible(viewer, name):
            assert_team(read_policy, viewer, name, team)
        else:
            assert team['name'] == REDACTED, f"{viewer} should not see {name}"
            assert team['parent'] is None
            assert not team['children']

    for name in TEAMS:
        team = await result_of(client, login_token_factory, read_policy, viewer, 'teamsTeam', by_id, {'id': read_policy[name]})
        assert int(team['id']) == read_policy[name]
        assert (team['name'] != REDACTED) == visible(viewer, name)


@pytest.mark.asyncio(loop_scope="session")
@pytest.mark.parametrize('viewer', [viewer for viewer in VIEWERS if viewer != 'anonymous'])
async def test_team_trees_with_teams_asked_for_in_the_same_request(client, login_token_factory, read_policy, viewer):
    """Teams loaded by id earlier in a request do not change the list of team trees"""
    response = await post_as(
        client, login_token_factory, read_policy.user(viewer),
        "query ($id: ID!) { "
        "  teamsTeam(id: $id) { status result { id } } "
        "  teamsRoots { status result { id } errors { name message } } "
        "}",
        {'id': read_policy['child']}
    )
    payload = get_verified_payload(response, 'teamsRoots')
    assert payload['status'] == GQLStatus.SUCCESS.name, payload['errors']
    ids = [team['id'] if team else None for team in payload['result']]
    assert None not in ids
    assert len(ids) == len(set(ids)), f"duplicate roots: {ids}"
    assert {read_policy[name] for name in ROOTS} <= {int(team_id) for team_id in ids}


@pytest.mark.asyncio(loop_scope="session")
@pytest.mark.parametrize('viewer', VIEWERS)
async def test_account(client, login_token_factory, read_policy, viewer):
    payload = await payload_of(
        client, login_token_factory, read_policy, viewer, 'accountsAccount',
        "query { accountsAccount { status result { user { id email } } errors { name message } } }"
    )
    if viewer == 'anonymous':
        assert payload['status'] != GQLStatus.SUCCESS.name
        assert payload['result'] is None
        return
    assert payload['status'] == GQLStatus.SUCCESS.name, payload['errors']
    assert int(payload['result']['user']['id']) == read_policy[viewer]


@pytest.mark.asyncio(loop_scope="session")
@pytest.mark.parametrize('viewer', VIEWERS)
async def test_user_access(client, login_token_factory, read_policy, viewer):
    payload = await payload_of(
        client, login_token_factory, read_policy, viewer, 'accountsUserAccess',
        "query { accountsUserAccess { status result { read { id } write { id } admin { id } curate { id } } errors { name message } } }"
    )
    if viewer == 'anonymous':
        assert payload['status'] != GQLStatus.SUCCESS.name
        assert payload['result'] is None
        return
    assert payload['status'] == GQLStatus.SUCCESS.name, payload['errors']
    for access in Access:
        teams = {int(team['id']) for team in payload['result'][access.name.lower()] or []}
        assert teams == {read_policy[team] for team, accesses in AFFILIATIONS[viewer].items() if access in accesses}, \
            f"{viewer}: {access.name} teams"
