"""
Persons under the read policy (docs/read-access.md and docs/person.md §3), on the read-policy scenario (PEOPLE in
tests/breedgraph/scenarios/read_policy_scenario.py).

A Person is seen in one of three views: FULL, the record, by read affiliates of its team and by its linked user;
ATTRIBUTION, name, institution and ORCID iD, by those reading it by release only; RESTRICTED, its id, by anyone else
asking for it by id, with their own request to be linked, if any, so they can withdraw it (rule 2). Persons are
released at most to registered users, so anonymous users see every Person restricted (and get no contacts or
contributions to meet them in). Searches leave restricted Persons out, so a name does not reveal that a hidden Person
has it (rule 5).
"""
import pytest

from breedgraph.domain.model.people import PersonView

from tests.breedgraph.scenarios.read_policy_scenario import VIEWERS, PEOPLE


def assert_person(read_policy, viewer: str, name: str, person):
    _, _, teams, linked_user, claimant = PEOPLE[name]
    view = read_policy.person_view(viewer, name)
    assert person.id == read_policy[name]
    assert person.view is PersonView(view), f"{viewer}: view of {name}"
    assert person.erased is False
    assert person.erased_at is None

    if view == 'FULL':
        assert person.name
        assert set(person.teams) == {read_policy[team] for team in teams}
        assert person.consent_attestation is True
        assert person.recorded_at is not None
        assert person.user == (read_policy[linked_user] if linked_user else None)
        assert person.linked is (linked_user is not None)
        assert person.claims == ([read_policy[claimant]] if claimant else [])
        return

    # outside the full view, nothing of the record-keeping, not even PersonBase's default attestation
    assert person.teams == []
    assert person.consent_attestation is None
    assert person.recorded_by is None
    assert person.recorded_at is None
    assert person.user is None
    assert person.linked is None
    # only the viewer's own request to be linked
    assert person.claims == ([read_policy[claimant]] if claimant == viewer else [])
    if view == 'ATTRIBUTION':
        assert person.name
    else:
        assert person.name is None
        assert person.institution is None
        assert person.orcid is None


def test_expected_views(read_policy):
    assert read_policy.person_view('outsider', 'person_outsider') == 'FULL'
    assert read_policy.person_view('outsider', 'person_claimed') == 'RESTRICTED'
    assert read_policy.person_view('outsider', 'person_public') == 'ATTRIBUTION'
    assert read_policy.person_view('anonymous', 'person_public') == 'RESTRICTED'
    assert read_policy.person_view('anonymous', 'person_other') == 'RESTRICTED'
    assert read_policy.person_view('stranger', 'person_other') == 'FULL'
    assert read_policy.person_view('admin', 'person_other') == 'ATTRIBUTION'
    assert read_policy.person_view('admin', 'person_claimed') == 'FULL'


@pytest.mark.asyncio(loop_scope="session")
@pytest.mark.parametrize('viewer', VIEWERS)
async def test_people_by_id(views_factory, read_policy, viewer):
    async with views_factory.get_views(user_id=read_policy.user(viewer)) as views:
        people = {person.id: person for person in await views.people.get_people([read_policy[name] for name in PEOPLE])}
    assert set(people) == {read_policy[name] for name in PEOPLE}
    for name in PEOPLE:
        assert_person(read_policy, viewer, name, people[read_policy[name]])


@pytest.mark.asyncio(loop_scope="session")
@pytest.mark.parametrize('viewer', VIEWERS)
async def test_search_leaves_restricted_out(views_factory, read_policy, viewer):
    async with views_factory.get_views(user_id=read_policy.user('admin')) as views:
        names = {person.id: person.name for person in await views.people.get_people([read_policy[name] for name in PEOPLE])}
    async with views_factory.get_views(user_id=read_policy.user(viewer)) as views:
        everyone = {person.id: person for person in await views.people.search_people()}
        expected = [name for name in PEOPLE if read_policy.person_view(viewer, name) != 'RESTRICTED']
        assert set(everyone) == {read_policy[name] for name in expected}
        for name in expected:
            assert_person(read_policy, viewer, name, everyone[read_policy[name]])
        # by name, ignoring case: a restricted Person's name finds nothing
        for name in PEOPLE:
            found = await views.people.search_people(names[read_policy[name]].upper())
            shown = read_policy.person_view(viewer, name) != 'RESTRICTED'
            assert [person.id for person in found] == ([read_policy[name]] if shown else []), \
                f"{viewer}: search for {name}"


@pytest.mark.asyncio(loop_scope="session")
@pytest.mark.parametrize('viewer', VIEWERS)
async def test_people_by_users(views_factory, read_policy, viewer):
    """The Persons linked to accounts, for attributing what accounts did; accounts without a Person are left out"""
    async with views_factory.get_views(user_id=read_policy.user(viewer)) as views:
        people = await views.people.get_people_by_users(
            [read_policy[user] for user in ('admin', 'writer', 'outsider', 'stranger')]
        )
    linked = {user: name for name, (_, _, _, user, _) in PEOPLE.items() if user is not None}
    assert set(people) == {read_policy[user] for user in linked}
    for user, name in linked.items():
        assert_person(read_policy, viewer, name, people[read_policy[user]])
