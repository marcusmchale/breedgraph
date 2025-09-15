import pytest
import pytest_asyncio

from src.breedgraph.domain.model.organisations import (
    TeamInput, TeamStored, Organisation,
    Access, Affiliation, Affiliations, Authorisation
)
from src.breedgraph.custom_exceptions import IllegalOperationError

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
def first_organisation(root_team, lorem_text_generator) -> Organisation:
    return Organisation(nodes=[root_team])

@pytest.mark.asyncio
async def test_get_organisation_root(first_organisation, root_team, first_child_team):
    assert first_organisation.root.id == root_team.id
    first_organisation.add_team(first_child_team, parent_id = first_organisation.root.id)
    assert first_organisation.root.id == root_team.id

@pytest.mark.asyncio
async def test_organisation_root_must_have_heritable_admin(first_organisation, root_team):
    root_team.affiliations.admin = dict()
    with pytest.raises(ValueError):
        Organisation(nodes=[root_team])

@pytest.mark.asyncio
async def test_remove_node(first_organisation, root_team, first_child_team):
    temp_id = first_organisation.add_team(first_child_team, first_organisation.root.id)
    first_organisation._remove_nodes([temp_id])
    assert first_organisation.size == 1

@pytest.mark.asyncio
async def test_team_parent_change(first_organisation, root_team, first_child_team, second_child_team):
    first_id = first_organisation.add_team(first_child_team, first_organisation.root.id)
    second_id = first_organisation.add_team(second_child_team, first_organisation.root.id)

    first_organisation.change_source(second_id, first_id)
    assert second_id in first_organisation.get_descendants(first_id)

@pytest.mark.asyncio
async def test_prevent_cycles(first_organisation, root_team, first_child_team):
    first_id = first_organisation.add_team(first_child_team, first_organisation.root.id)
    with pytest.raises(IllegalOperationError):
        first_organisation.change_source(root_team.id, first_id)

@pytest.mark.asyncio
async def test_request_affiliation_should_fail_unless_agent_is_user(first_organisation, root_team):
    with pytest.raises(IllegalOperationError):
        first_organisation.request_affiliation(agent_id=1, team_id=1, user_id=2, access=Access.ADMIN)

@pytest.mark.asyncio
async def test_request_affiliation(first_organisation, root_team):
    first_organisation.request_affiliation(agent_id=2, team_id=1, user_id=2, access=Access.ADMIN)
    affiliates = first_organisation.get_affiliates(team_id=1, access=Access.ADMIN, authorisation=Authorisation.REQUESTED)
    assert 2 in affiliates

@pytest.mark.asyncio
async def test_remove_affiliation_by_admin(first_organisation, root_team):
    first_organisation.request_affiliation(agent_id=2, team_id=1, user_id=2, access=Access.ADMIN)
    first_organisation.remove_affiliation(agent_id=1, team_id=1, user_id=2, access=Access.ADMIN)
    affiliates = first_organisation.get_affiliates(team_id=1)
    assert 2 not in affiliates

@pytest.mark.asyncio
async def test_remove_affiliation_by_user(first_organisation, root_team):
    first_organisation.request_affiliation(agent_id=2, team_id=1, user_id=2, access=Access.ADMIN)
    first_organisation.remove_affiliation(agent_id=2, team_id=1, user_id=2, access=Access.ADMIN)
    affiliates = first_organisation.get_affiliates(team_id=1, authorisation=Authorisation.REVOKED)
    assert 2 not in affiliates

@pytest.mark.asyncio
async def test_revoke_affiliation_by_admin(first_organisation, root_team):
    first_organisation.request_affiliation(agent_id=2, team_id=1, user_id=2, access=Access.ADMIN)
    first_organisation.revoke_affiliation(agent_id=1, team_id=1, user_id=2, access=Access.ADMIN)
    affiliates_authorised = first_organisation.get_affiliates(team_id=1)
    assert 2 not in affiliates_authorised
    affiliates_all = first_organisation.get_affiliates(team_id=1, authorisation=Authorisation.REVOKED)
    assert 2 in affiliates_all