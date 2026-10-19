"""
The people queries under the read policy, through GraphQL, on the read-policy scenario
(see tests/breedgraph/integration/views/test_people_view.py for the view underneath).

They need an account, and anonymous users meet no Persons at all: Persons are released at most to registered users,
and anonymous users get no contacts or contributors (docs/person.md §3). In the full view, a Person's teams hidden from the viewer are stood in for by the
nearest team they can see (rule 7): a team tree's root is visible to every signed-in user, its other teams only to
their affiliates.
"""
import pytest

from breedgraph.entrypoints.fastapi.graphql.decorators import GQLStatus

from tests.breedgraph.e2e.utils import post_as, get_verified_payload
from tests.breedgraph.scenarios.read_policy_scenario import VIEWERS, PEOPLE

PERSON_FIELDS = (
    "id view name restricted erased erasedAt informedAttestation linked recordedAt "
    "teams { team { id } standIn }"
)

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


def expected_team_references(read_policy, viewer: str, teams: list[str]) -> set[tuple[int, bool]]:
    references = set()
    for team in teams:
        if team in TEAM_AFFILIATES and viewer not in TEAM_AFFILIATES[team]:
            references.add((read_policy[STAND_INS[team]], True))
        else:
            references.add((read_policy[team], False))
    return references


def assert_person(read_policy, viewer: str, name: str, person: dict):
    view = read_policy.person_view(viewer, name)
    assert int(person['id']) == read_policy[name]
    assert person['view'] == view, f"{viewer}: view of {name}"
    assert person['restricted'] is (view == 'RESTRICTED')
    assert person['erased'] is False
    assert person['erasedAt'] is None
    if view == 'FULL':
        assert person['name']
        assert person['informedAttestation'] is True
        assert person['linked'] is (PEOPLE[name][3] is not None)
        assert person['recordedAt']
        assert {(int(reference['team']['id']), reference['standIn']) for reference in person['teams']} == \
            expected_team_references(read_policy, viewer, PEOPLE[name][2]), f"{viewer}: teams of {name}"
        return
    assert person['teams'] == []
    assert person['informedAttestation'] is None
    assert person['linked'] is None
    assert person['recordedAt'] is None
    if view == 'ATTRIBUTION':
        assert person['name']
    else:
        assert person['name'] is None


async def assert_refused_anonymously(client, login_token_factory, read_policy, operation: str, text: str, variables=None):
    payload = await payload_of(client, login_token_factory, read_policy, 'anonymous', operation, text, variables)
    assert payload['status'] != GQLStatus.SUCCESS.name
    assert payload['result'] is None


@pytest.mark.asyncio(loop_scope="session")
@pytest.mark.parametrize('viewer', VIEWERS)
async def test_people_by_id(client, login_token_factory, read_policy, viewer):
    by_ids = f"query ($ids: [ID!]!) {{ peoplePeople(ids: $ids) {{ status result {{ {PERSON_FIELDS} }} errors {{ name message }} }} }}"
    by_id = f"query ($id: ID!) {{ peoplePerson(id: $id) {{ status result {{ {PERSON_FIELDS} }} errors {{ name message }} }} }}"
    if viewer == 'anonymous':
        # stepping through ids would list every public Person
        await assert_refused_anonymously(
            client, login_token_factory, read_policy, 'peoplePeople', by_ids, {'ids': [read_policy[name] for name in PEOPLE]}
        )
        await assert_refused_anonymously(
            client, login_token_factory, read_policy, 'peoplePerson', by_id, {'id': read_policy['person_public']}
        )
        return
    result = await result_of(
        client, login_token_factory, read_policy, viewer, 'peoplePeople', by_ids,
        {'ids': [read_policy[name] for name in PEOPLE]}
    )
    people = {int(person['id']): person for person in result}
    assert set(people) == {read_policy[name] for name in PEOPLE}
    for name in PEOPLE:
        assert_person(read_policy, viewer, name, people[read_policy[name]])

    for name in PEOPLE:
        person = await result_of(
            client, login_token_factory, read_policy, viewer, 'peoplePerson', by_id, {'id': read_policy[name]}
        )
        assert_person(read_policy, viewer, name, person)


@pytest.mark.asyncio(loop_scope="session")
@pytest.mark.parametrize('viewer', VIEWERS)
async def test_people_search(client, login_token_factory, read_policy, viewer):
    search = f"query {{ people {{ status result {{ {PERSON_FIELDS} }} errors {{ name message }} }} }}"
    if viewer == 'anonymous':
        # no public directory of people
        await assert_refused_anonymously(client, login_token_factory, read_policy, 'people', search)
        return
    result = await result_of(client, login_token_factory, read_policy, viewer, 'people', search)
    people = {int(person['id']): person for person in result}
    expected = [name for name in PEOPLE if read_policy.person_view(viewer, name) != 'RESTRICTED']
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
        # the linked user sees their own Person in full, whatever its release
        assert_person(read_policy, viewer, mine[0], payload['result'])
        assert payload['result']['view'] == 'FULL'
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


@pytest.mark.asyncio(loop_scope="session")
@pytest.mark.parametrize('viewer', VIEWERS)
async def test_people_in_context(client, login_token_factory, read_policy, viewer):
    """
    Persons as contributors of a readable dataset, in the signed-in viewer's view of each, restricted ones too.
    Anonymous users get no contributors
    """
    result = await result_of(
        client, login_token_factory, read_policy, viewer, 'datasets',
        f"query ($ids: [ID!]) {{ datasets(ids: $ids) {{ status result {{ id contributions {{ person {{ {PERSON_FIELDS} }} }} }} errors {{ name message }} }} }}",
        {'ids': [read_policy['dataset_public']]}
    )
    [dataset] = result
    if viewer == 'anonymous':
        assert dataset['contributions'] == []
        return
    contributors = {int(c['person']['id']): c['person'] for c in dataset['contributions']}
    assert set(contributors) == {read_policy[name] for name in ('person_public', 'person_private')}
    for name in ('person_public', 'person_private'):
        assert_person(read_policy, viewer, name, contributors[read_policy[name]])
