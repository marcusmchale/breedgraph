"""
Persons under the read policy (docs/read-access.md and docs/person.md), on the read-policy scenario (PEOPLE in
tests/breedgraph/scenarios/read_policy_scenario.py).

A Person the viewer can read, or is linked to, is returned in full. Any other Person asked for by id is a placeholder:
its id with no name or teams, and the viewer's own request to be linked, if any, so they can withdraw it (rule 2).
Searches leave such Persons out, so a name does not reveal that a hidden Person has it (rule 5).
"""
import pytest

from tests.breedgraph.scenarios.read_policy_scenario import VIEWERS, PEOPLE


def shown(read_policy, viewer: str, name: str) -> bool:
    """Whether the viewer sees the Person in full: they can read it or are linked to it"""
    return read_policy.readable(viewer, name) or PEOPLE[name][3] == viewer


def assert_person(read_policy, viewer: str, name: str, person):
    _, _, teams, linked_user, claimant = PEOPLE[name]
    assert person.id == read_policy[name]
    if shown(read_policy, viewer, name):
        assert person.name
        assert set(person.teams) == {read_policy[team] for team in teams}
        assert person.user == (read_policy[linked_user] if linked_user else None)
        assert person.claims == ([read_policy[claimant]] if claimant else [])
    else:
        assert person.name is None
        assert person.institution is None
        assert person.teams == []
        assert person.user is None
        # only the viewer's own request to be linked
        assert person.claims == ([read_policy[claimant]] if claimant == viewer else [])


def test_expected_shapes(read_policy):
    assert shown(read_policy, 'outsider', 'person_outsider')
    assert not shown(read_policy, 'outsider', 'person_claimed')
    assert not shown(read_policy, 'anonymous', 'person_other')
    assert shown(read_policy, 'admin', 'person_claimed')


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
async def test_search_leaves_hidden_out(views_factory, read_policy, viewer):
    async with views_factory.get_views(user_id=read_policy.user('admin')) as views:
        names = {person.id: person.name for person in await views.people.get_people([read_policy[name] for name in PEOPLE])}
    async with views_factory.get_views(user_id=read_policy.user(viewer)) as views:
        everyone = {person.id: person for person in await views.people.search_people()}
        expected = [name for name in PEOPLE if shown(read_policy, viewer, name)]
        assert set(everyone) == {read_policy[name] for name in expected}
        for name in expected:
            assert_person(read_policy, viewer, name, everyone[read_policy[name]])
        # by name, ignoring case: a hidden Person's name finds nothing
        for name in PEOPLE:
            found = await views.people.search_people(names[read_policy[name]].upper())
            assert [person.id for person in found] == ([read_policy[name]] if shown(read_policy, viewer, name) else []), \
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
