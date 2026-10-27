import pytest
import pytest_asyncio

from breedgraph.domain.model.team_trees import (
    TeamInput, TeamStored, TeamTree,
    Affiliation, Affiliations, Authorisation
)
from breedgraph.domain.model import Access
from breedgraph.domain.events.accounts import AffiliationRequested
from breedgraph.custom_exceptions import IllegalOperationError, UnauthorisedOperationError

def get_team_input(lorem_text_generator) -> TeamInput:
    return TeamInput(name=lorem_text_generator.new_text(5), fullname = lorem_text_generator.new_text(10))

@pytest_asyncio.fixture
def root_team(lorem_text_generator) -> TeamStored:
    root_team = get_team_input(lorem_text_generator)
    affiliations = Affiliations()
    affiliations.set_by_access(Access.ADMIN, 1, Affiliation(authorisation=Authorisation.AUTHORISED, heritable=True))
    return TeamStored(
        id=1,
        affiliations=affiliations,
        **root_team.model_dump()
    )

@pytest_asyncio.fixture
def first_child_team(lorem_text_generator) -> TeamInput:
    return get_team_input(lorem_text_generator)

@pytest_asyncio.fixture
def second_child_team(lorem_text_generator) -> TeamInput:
    return get_team_input(lorem_text_generator)

@pytest_asyncio.fixture
def first_team_tree(root_team, lorem_text_generator) -> TeamTree:
    return TeamTree(nodes=[root_team])

@pytest.mark.asyncio
async def test_get_team_tree_root(first_team_tree, root_team, first_child_team):
    assert first_team_tree.root.id == root_team.id
    first_team_tree.add_team(first_child_team, parent_id = first_team_tree.root.id)
    assert first_team_tree.root.id == root_team.id

@pytest.mark.asyncio
async def test_team_tree_root_must_have_heritable_admin(first_team_tree, root_team):
    root_team.affiliations.admin = dict()
    with pytest.raises(ValueError):
        TeamTree(nodes=[root_team])

@pytest.mark.asyncio
async def test_remove_node(first_team_tree, root_team, first_child_team):
    temp_id = first_team_tree.add_team(first_child_team, first_team_tree.root.id)
    first_team_tree._remove_nodes([temp_id])
    assert first_team_tree.size == 1

@pytest.mark.asyncio
async def test_team_parent_change(first_team_tree, root_team, first_child_team, second_child_team):
    first_id = first_team_tree.add_team(first_child_team, first_team_tree.root.id)
    second_id = first_team_tree.add_team(second_child_team, first_team_tree.root.id)

    first_team_tree.change_source(second_id, first_id)
    assert second_id in first_team_tree.get_descendants(first_id)

@pytest.mark.asyncio
async def test_prevent_cycles(first_team_tree, root_team, first_child_team):
    first_id = first_team_tree.add_team(first_child_team, first_team_tree.root.id)
    with pytest.raises(IllegalOperationError):
        first_team_tree.change_source(root_team.id, first_id)

@pytest.mark.asyncio
async def test_request_affiliation_should_fail_unless_agent_is_user(first_team_tree, root_team):
    with pytest.raises(IllegalOperationError):
        first_team_tree.request_affiliation(agent_id=1, team_id=1, user_id=2, access=Access.ADMIN)

@pytest.mark.asyncio
async def test_request_affiliation(first_team_tree, root_team):
    first_team_tree.request_affiliation(agent_id=2, team_id=1, user_id=2, access=Access.ADMIN)
    affiliates = first_team_tree.get_affiliates(team_id=1, access=Access.ADMIN, authorisation=Authorisation.REQUESTED)
    assert 2 in affiliates
    assert [type(event) for event in first_team_tree.events] == [AffiliationRequested]

@pytest.mark.asyncio
async def test_an_admins_own_request_is_authorised_at_once(first_team_tree):
    # with read access to the same extent, as when another admin authorises curate access; no one is asked
    first_team_tree.request_affiliation(agent_id=1, team_id=1, user_id=1, access=Access.CURATE, heritable=True)
    affiliations = first_team_tree.get_team(1).affiliations
    authorised = Affiliation(authorisation=Authorisation.AUTHORISED, heritable=True)
    assert affiliations.get_by_access(Access.CURATE)[1] == authorised
    assert affiliations.get_by_access(Access.READ)[1] == authorised
    assert not first_team_tree.events

@pytest_asyncio.fixture
def lab_tree(root_team, lorem_text_generator) -> TeamTree:
    """The root, with user 1 its heritable admin; a lab below it that user 2 administers, the lab only; a project below"""
    lab_admin = Affiliations()
    for access in (Access.ADMIN, Access.READ):
        lab_admin.set_by_access(access, 2, Affiliation(authorisation=Authorisation.AUTHORISED, heritable=False))
    lab = TeamStored(id=2, affiliations=lab_admin, **get_team_input(lorem_text_generator).model_dump())
    project = TeamStored(id=3, affiliations=Affiliations(), **get_team_input(lorem_text_generator).model_dump())
    return TeamTree(nodes=[root_team, lab, project], edges=[(1, 2, {}), (2, 3, {})])

@pytest.mark.asyncio
async def test_heritable_affiliations_are_authorised_only_by_admins_for_every_team_below(lab_tree):
    lab_tree.request_affiliation(agent_id=4, team_id=2, user_id=4, access=Access.READ, heritable=True)
    with pytest.raises(UnauthorisedOperationError):
        lab_tree.authorise_affiliation(agent_id=2, team_id=2, user_id=4, access=Access.READ, heritable=True)
    assert 4 not in lab_tree.get_affiliates(team_id=3, access=Access.READ)
    # the lab's admin may authorise it for the lab only, and the root's heritable admin as asked
    lab_tree.authorise_affiliation(agent_id=2, team_id=2, user_id=4, access=Access.READ, heritable=False)
    assert 4 not in lab_tree.get_affiliates(team_id=3, access=Access.READ)
    lab_tree.authorise_affiliation(agent_id=1, team_id=2, user_id=4, access=Access.READ, heritable=True)
    assert 4 in lab_tree.get_affiliates(team_id=3, access=Access.READ)

@pytest.mark.asyncio
async def test_an_admins_own_heritable_request_waits_unless_they_administer_every_team_below(lab_tree):
    lab_tree.request_affiliation(agent_id=2, team_id=2, user_id=2, access=Access.CURATE, heritable=True)
    assert 2 in lab_tree.get_affiliates(team_id=2, access=Access.CURATE, authorisation=Authorisation.REQUESTED)
    assert 2 not in lab_tree.get_affiliates(team_id=3, access=Access.CURATE)
    assert [type(event) for event in lab_tree.events] == [AffiliationRequested]

    # once they administer the project too, their own heritable request is authorised at once
    lab_tree.events.clear()
    lab_tree.request_affiliation(agent_id=2, team_id=3, user_id=2, access=Access.ADMIN)
    lab_tree.authorise_affiliation(agent_id=1, team_id=3, user_id=2, access=Access.ADMIN)
    lab_tree.remove_affiliation(agent_id=2, team_id=2, user_id=2, access=Access.CURATE)
    lab_tree.events.clear()
    lab_tree.request_affiliation(agent_id=2, team_id=2, user_id=2, access=Access.CURATE, heritable=True)
    assert 2 in lab_tree.get_affiliates(team_id=3, access=Access.CURATE)
    assert not lab_tree.events

@pytest.mark.asyncio
async def test_remove_affiliation_by_admin(first_team_tree, root_team):
    first_team_tree.request_affiliation(agent_id=2, team_id=1, user_id=2, access=Access.ADMIN)
    first_team_tree.remove_affiliation(agent_id=1, team_id=1, user_id=2, access=Access.ADMIN)
    affiliates = first_team_tree.get_affiliates(team_id=1)
    assert 2 not in affiliates

@pytest.mark.asyncio
async def test_remove_affiliation_by_user(first_team_tree, root_team):
    first_team_tree.request_affiliation(agent_id=2, team_id=1, user_id=2, access=Access.ADMIN)
    first_team_tree.remove_affiliation(agent_id=2, team_id=1, user_id=2, access=Access.ADMIN)
    affiliates = first_team_tree.get_affiliates(team_id=1, authorisation=Authorisation.REVOKED)
    assert 2 not in affiliates

@pytest.mark.asyncio
async def test_revoke_affiliation_by_admin(first_team_tree, root_team):
    first_team_tree.request_affiliation(agent_id=2, team_id=1, user_id=2, access=Access.ADMIN)
    first_team_tree.revoke_affiliation(agent_id=1, team_id=1, user_id=2, access=Access.ADMIN)
    affiliates_authorised = first_team_tree.get_affiliates(team_id=1)
    assert 2 not in affiliates_authorised
    affiliates_all = first_team_tree.get_affiliates(team_id=1, authorisation=Authorisation.REVOKED)
    assert 2 in affiliates_all

@pytest.mark.asyncio
@pytest.mark.parametrize("access", [Access.CURATE, Access.ADMIN])
async def test_authorise_curate_or_admin_includes_read(first_team_tree, access):
    first_team_tree.request_affiliation(agent_id=2, team_id=1, user_id=2, access=access)
    first_team_tree.authorise_affiliation(agent_id=1, team_id=1, user_id=2, access=access, heritable=True)
    assert 2 in first_team_tree.get_affiliates(team_id=1, access=access)
    assert 2 in first_team_tree.get_affiliates(team_id=1, access=Access.READ)
    read_affiliation = first_team_tree.get_team(1).affiliations.get_by_access(Access.READ)[2]
    assert read_affiliation.heritable is True

@pytest.mark.asyncio
@pytest.mark.parametrize("access", [Access.CURATE, Access.ADMIN])
async def test_authorise_curate_or_admin_for_the_team_only_keeps_heritable_read(first_team_tree, access):
    first_team_tree.request_affiliation(agent_id=2, team_id=1, user_id=2, access=Access.READ, heritable=True)
    first_team_tree.authorise_affiliation(agent_id=1, team_id=1, user_id=2, access=Access.READ, heritable=True)
    first_team_tree.request_affiliation(agent_id=2, team_id=1, user_id=2, access=access)
    first_team_tree.authorise_affiliation(agent_id=1, team_id=1, user_id=2, access=access, heritable=False)
    assert first_team_tree.get_team(1).affiliations.get_by_access(access)[2].heritable is False
    assert first_team_tree.get_team(1).affiliations.get_by_access(Access.READ)[2].heritable is True

@pytest.mark.asyncio
async def test_authorise_write_does_not_include_read(first_team_tree):
    first_team_tree.request_affiliation(agent_id=2, team_id=1, user_id=2, access=Access.WRITE)
    first_team_tree.authorise_affiliation(agent_id=1, team_id=1, user_id=2, access=Access.WRITE, heritable=False)
    assert 2 not in first_team_tree.get_affiliates(team_id=1, access=Access.READ)

@pytest.mark.asyncio
async def test_revoke_read_from_admin_is_refused(first_team_tree):
    first_team_tree.request_affiliation(agent_id=2, team_id=1, user_id=2, access=Access.ADMIN)
    first_team_tree.authorise_affiliation(agent_id=1, team_id=1, user_id=2, access=Access.ADMIN, heritable=False)
    with pytest.raises(IllegalOperationError):
        first_team_tree.revoke_affiliation(agent_id=1, team_id=1, user_id=2, access=Access.READ)
    # once admin access is revoked, read access can be revoked
    first_team_tree.revoke_affiliation(agent_id=1, team_id=1, user_id=2, access=Access.ADMIN)
    first_team_tree.revoke_affiliation(agent_id=1, team_id=1, user_id=2, access=Access.READ)
    assert 2 not in first_team_tree.get_affiliates(team_id=1, access=Access.READ)

@pytest.mark.asyncio
async def test_read_cannot_be_revoked_or_removed_while_curate_is_authorised(first_team_tree):
    """Curate access includes read access, as admin access does, so read goes last (and curate no longer goes with it)"""
    first_team_tree.request_affiliation(agent_id=2, team_id=1, user_id=2, access=Access.CURATE)
    first_team_tree.authorise_affiliation(agent_id=1, team_id=1, user_id=2, access=Access.CURATE, heritable=False)
    with pytest.raises(IllegalOperationError):
        first_team_tree.revoke_affiliation(agent_id=1, team_id=1, user_id=2, access=Access.READ)
    with pytest.raises(IllegalOperationError):
        first_team_tree.remove_affiliation(agent_id=2, team_id=1, user_id=2, access=Access.READ)
    assert 2 in first_team_tree.get_affiliates(team_id=1, access=Access.CURATE)
    assert 2 in first_team_tree.get_affiliates(team_id=1, access=Access.READ)

    # removing curate leaves read in place; then read can go
    first_team_tree.remove_affiliation(agent_id=2, team_id=1, user_id=2, access=Access.CURATE)
    assert 2 in first_team_tree.get_affiliates(team_id=1, access=Access.READ)
    first_team_tree.remove_affiliation(agent_id=2, team_id=1, user_id=2, access=Access.READ)
    assert 2 not in first_team_tree.get_affiliates(team_id=1, access=Access.READ)

@pytest.mark.asyncio
async def test_read_cannot_be_removed_while_admin_is_authorised(first_team_tree):
    first_team_tree.request_affiliation(agent_id=2, team_id=1, user_id=2, access=Access.ADMIN)
    first_team_tree.authorise_affiliation(agent_id=1, team_id=1, user_id=2, access=Access.ADMIN, heritable=False)
    with pytest.raises(IllegalOperationError):
        first_team_tree.remove_affiliation(agent_id=2, team_id=1, user_id=2, access=Access.READ)
    first_team_tree.remove_affiliation(agent_id=2, team_id=1, user_id=2, access=Access.ADMIN)
    first_team_tree.remove_affiliation(agent_id=2, team_id=1, user_id=2, access=Access.READ)
    assert 2 not in first_team_tree.get_affiliates(team_id=1, access=Access.READ)

@pytest.mark.asyncio
async def test_hidden_teams_map_to_the_nearest_visible_team(root_team, lorem_text_generator):
    # a team hidden from the user is shown as the nearest team they can see that includes it, even when its parent is
    # hidden too and comes after it in the graph
    grandchild = TeamStored(id=3, affiliations=Affiliations(), **get_team_input(lorem_text_generator).model_dump())
    child = TeamStored(id=2, affiliations=Affiliations(), **get_team_input(lorem_text_generator).model_dump())
    team_tree = TeamTree(nodes=[root_team, grandchild, child], edges=[(1, 2, {}), (2, 3, {})])
    output_map = team_tree.redacted(user_id=2).to_output_map()
    assert {team_id: team.id for team_id, team in output_map.items()} == {1: 1, 2: 1, 3: 1}


@pytest.mark.asyncio
async def test_teams_below_the_root_are_visible_only_to_affiliates(root_team, lorem_text_generator):
    reader = Affiliations()
    reader.set_by_access(Access.READ, 2, Affiliation(authorisation=Authorisation.AUTHORISED, heritable=True))
    child = TeamStored(id=2, affiliations=reader, **get_team_input(lorem_text_generator).model_dump())
    grandchild = TeamStored(id=3, affiliations=Affiliations(), **get_team_input(lorem_text_generator).model_dump())
    hidden = TeamStored(id=4, affiliations=Affiliations(), **get_team_input(lorem_text_generator).model_dump())
    team_tree = TeamTree(nodes=[root_team, child, grandchild, hidden], edges=[(1, 2, {}), (2, 3, {}), (1, 4, {})])

    assert team_tree.visible_team_ids(None) == {1}
    assert team_tree.visible_team_ids(2) == {1, 2, 3}  # the grandchild by heritable read on the child
    assert team_tree.visible_team_ids(1) == {1, 2, 3, 4}  # heritable admin on the root
    # the repository returns whole team trees, redaction is only for reading
    assert {team.id for team in team_tree.redacted(user_id=2).teams} == {1, 2, 3}
    assert {team.id for team in team_tree.teams} == {1, 2, 3, 4}


@pytest.mark.asyncio
async def test_whole_team_tree_refuses_removing_a_team_with_hidden_children(root_team, lorem_text_generator):
    child = TeamStored(id=2, affiliations=Affiliations(), **get_team_input(lorem_text_generator).model_dump())
    grandchild = TeamStored(id=3, affiliations=Affiliations(), **get_team_input(lorem_text_generator).model_dump())
    team_tree = TeamTree(nodes=[root_team, child, grandchild], edges=[(1, 2, {}), (2, 3, {})])
    with pytest.raises(IllegalOperationError):
        team_tree.remove_team(2)
