"""
The people queries under the read policy, through GraphQL, on the read-policy scenario
(see tests/breedgraph/integration/views/test_people_view.py for the view underneath).

They answer anonymous requests, except those about the viewer's own Person and requests. A Person's teams hidden
from the viewer are stood in for by the nearest team they can see (rule 7): a team tree's root is visible to
everyone, its other teams only to their affiliates.
"""
import pytest

from breedgraph.entrypoints.fastapi.graphql.decorators import GQLStatus

from tests.breedgraph.e2e.utils import post_as, get_verified_payload
from tests.breedgraph.scenarios.read_policy_scenario import VIEWERS, PEOPLE

PERSON_FIELDS = "id name restricted erased teams { team { id } standIn }"

# who can see each team, and the team that stands in for it otherwise
TEAM_AFFILIATES = {'child': ('admin', 'writer')}
STAND_INS = {'child': 'root'}


async def payload_of(client, login_token_factory, read_policy, viewer: str, operation: str, text: str, variables=None):
    response = await post_as(client, login_token_factory, read_policy.user(viewer), text, variables)
    return get_verified_payload(response, operation)


async def result_of(client, login_token_factory, read_policy, viewer: str, operation: str, text: str, variables=None):
    payload = await payload_of(client, login_token_factory, read_policy, viewer, operation, text, variables)
    # an empty list or null is a valid result here, so not assert_payload_success
    assert payload['status'] == GQLStatus.SUCCESS.name, payload['errors']
    assert payload['errors'] is None
    return payload['result']


def shown(read_policy, viewer: str, name: str) -> bool:
    return read_policy.readable(viewer, name) or PEOPLE[name][3] == viewer


def expected_team_references(read_policy, viewer: str, teams: list[str]) -> set[tuple[int, bool]]:
    references = set()
    for team in teams:
        if team in TEAM_AFFILIATES and viewer not in TEAM_AFFILIATES[team]:
            references.add((read_policy[STAND_INS[team]], True))
        else:
            references.add((read_policy[team], False))
    return references


def assert_person(read_policy, viewer: str, name: str, person: dict):
    assert int(person['id']) == read_policy[name]
    assert person['erased'] is False
    if shown(read_policy, viewer, name):
        assert person['name']
        assert person['restricted'] is False
        assert {(int(reference['team']['id']), reference['standIn']) for reference in person['teams']} == \
            expected_team_references(read_policy, viewer, PEOPLE[name][2]), f"{viewer}: teams of {name}"
    else:
        assert person['name'] is None
        assert person['restricted'] is True
        assert person['teams'] == []


@pytest.mark.asyncio(loop_scope="session")
@pytest.mark.parametrize('viewer', VIEWERS)
async def test_people_by_id(client, login_token_factory, read_policy, viewer):
    result = await result_of(
        client, login_token_factory, read_policy, viewer, 'peoplePeople',
        f"query ($ids: [ID!]!) {{ peoplePeople(ids: $ids) {{ status result {{ {PERSON_FIELDS} }} errors {{ name message }} }} }}",
        {'ids': [read_policy[name] for name in PEOPLE]}
    )
    people = {int(person['id']): person for person in result}
    assert set(people) == {read_policy[name] for name in PEOPLE}
    for name in PEOPLE:
        assert_person(read_policy, viewer, name, people[read_policy[name]])

    for name in PEOPLE:
        person = await result_of(
            client, login_token_factory, read_policy, viewer, 'peoplePerson',
            f"query ($id: ID!) {{ peoplePerson(id: $id) {{ status result {{ {PERSON_FIELDS} }} errors {{ name message }} }} }}",
            {'id': read_policy[name]}
        )
        assert_person(read_policy, viewer, name, person)


@pytest.mark.asyncio(loop_scope="session")
@pytest.mark.parametrize('viewer', VIEWERS)
async def test_people_search(client, login_token_factory, read_policy, viewer):
    result = await result_of(
        client, login_token_factory, read_policy, viewer, 'people',
        f"query {{ people {{ status result {{ {PERSON_FIELDS} }} errors {{ name message }} }} }}"
    )
    people = {int(person['id']): person for person in result}
    expected = [name for name in PEOPLE if shown(read_policy, viewer, name)]
    assert set(people) == {read_policy[name] for name in expected}
    for name in expected:
        assert_person(read_policy, viewer, name, people[read_policy[name]])


@pytest.mark.asyncio(loop_scope="session")
@pytest.mark.parametrize('viewer', VIEWERS)
async def test_my_person(client, login_token_factory, read_policy, viewer):
    payload = await payload_of(
        client, login_token_factory, read_policy, viewer, 'peopleMyPerson',
        f"query {{ peopleMyPerson {{ status result {{ {PERSON_FIELDS} }} errors {{ name message }} }} }}"
    )
    if viewer == 'anonymous':
        assert payload['status'] != GQLStatus.SUCCESS.name
        assert payload['result'] is None
        return
    assert payload['status'] == GQLStatus.SUCCESS.name, payload['errors']
    mine = [name for name, (_, _, _, user, _) in PEOPLE.items() if user == viewer]
    if mine:
        assert int(payload['result']['id']) == read_policy[mine[0]]
        assert payload['result']['name']
    else:
        assert payload['result'] is None


@pytest.mark.asyncio(loop_scope="session")
@pytest.mark.parametrize('viewer', VIEWERS)
async def test_my_claims(client, login_token_factory, read_policy, viewer):
    """A user's own request to be linked shows the Person as they can see it: a placeholder where hidden"""
    payload = await payload_of(
        client, login_token_factory, read_policy, viewer, 'peopleMyClaims',
        f"query {{ peopleMyClaims {{ status result {{ person {{ {PERSON_FIELDS} }} requestedAt }} errors {{ name message }} }} }}"
    )
    if viewer == 'anonymous':
        assert payload['status'] != GQLStatus.SUCCESS.name
        assert payload['result'] is None
        return
    assert payload['status'] == GQLStatus.SUCCESS.name, payload['errors']
    claimed = [name for name, (_, _, _, _, claimant) in PEOPLE.items() if claimant == viewer]
    assert {int(claim['person']['id']) for claim in payload['result']} == {read_policy[name] for name in claimed}
    for claim in payload['result']:
        name = next(name for name in claimed if read_policy[name] == int(claim['person']['id']))
        assert_person(read_policy, viewer, name, claim['person'])
        assert claim['requestedAt']
