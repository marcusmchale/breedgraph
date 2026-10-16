"""
Repositories return whole aggregates, so writes see members the writer cannot read,
and linking requires read access to both ends.

The location tree below, with the teams that control each location and the release:

    country (A, public)
    ├── parent (A, registered)
    │   └── hidden (C, private)
    │       └── shared (B, registered)
    └── childless_but_hidden (A, registered)
        └── hidden_only_child (C, private)

    other_country (A, public)
    └── hidden_in_other_country (C, private)

User A writes for team A, user B for teams B and C, and user D curates and writes for team B only:
D can change "shared" but cannot read "hidden", its parent.
"""
import pytest
import pytest_asyncio

from breedgraph.custom_exceptions import UnauthorisedOperationError, IllegalOperationError, ProtectedNodeError
from breedgraph.domain.model.controls import Access, ReadRelease
from breedgraph.domain.model.location_trees import LocationInput

from tests.breedgraph.scenarios import AccountBuilder, OntologyBuilder, LocationTreeBuilder
from tests.breedgraph.scenarios.team_tree_builder import TeamTreeBuilder
from tests.breedgraph.scenarios.authorisation_manager import AuthorisationManager
from tests.breedgraph.utilities.inputs import LoremTextGenerator
from breedgraph.domain.model.accounts import OntologyRole

text = LoremTextGenerator()


async def _add_location(uow_factory, user_id: int, team_id: int, release: ReadRelease, parent_id: int, type_id: int) -> int:
    before = set(await _children(uow_factory, parent_id))
    async with uow_factory.get_uow(user_id=user_id, write_team=team_id, release=release) as uow:
        location_tree = await uow.repositories.location_trees.get(location_id=parent_id)
        location_tree.add_location(LocationInput(name=text.new_text(10), type=type_id), parent_id=parent_id)
        await uow.commit()
    added = set(await _children(uow_factory, parent_id)) - before
    assert len(added) == 1
    return added.pop()


# Read without a user: the repositories return whole aggregates, found by id
async def _children(uow_factory, location_id: int) -> list[int]:
    async with uow_factory.get_uow() as uow:
        location_tree = await uow.repositories.location_trees.get(location_id=location_id)
        return list(location_tree._graph.successors(location_id))


async def _parents(uow_factory, location_id: int) -> list[int]:
    async with uow_factory.get_uow() as uow:
        location_tree = await uow.repositories.location_trees.get(location_id=location_id)
        return list(location_tree._graph.predecessors(location_id))


@pytest_asyncio.fixture(scope="module", loop_scope="session")
async def integrity_context(isolated_state, uow_factory, state_store):
    accounts = AccountBuilder(uow_factory=uow_factory)
    a = await accounts.account_with_affiliations(ontology_role=OntologyRole.ADMIN)
    b = await accounts.account_with_affiliations()
    team_c = await TeamTreeBuilder(uow_factory=uow_factory).team_tree(user_id=b['user_id'])
    for access in Access:
        await TeamTreeBuilder(uow_factory=uow_factory).authorise_access(b['user_id'], team_c, access)
    user_d = await accounts.account()
    for access in (Access.READ, Access.WRITE, Access.CURATE):
        await AuthorisationManager(uow_factory).authorise_affiliation(
            agent_id=b['user_id'], user_id=user_d, team_id=b['team_id'], access=access
        )
    type_id = (await OntologyBuilder(uow_factory=uow_factory).location_types(user_id=a['user_id']))['ontology_location_state']

    countries = []
    for _ in range(2):
        async with uow_factory.get_uow(user_id=a['user_id'], write_team=a['team_id'], release=ReadRelease.PUBLIC) as uow:
            location_tree = await LocationTreeBuilder(uow_factory, state_store).location_tree_from_country(uow)
            await uow.commit()
            countries.append(location_tree.get_root_id())
    country, other_country = countries

    parent = await _add_location(uow_factory, a['user_id'], a['team_id'], ReadRelease.REGISTERED, country, type_id)
    hidden = await _add_location(uow_factory, b['user_id'], team_c, ReadRelease.PRIVATE, parent, type_id)
    shared = await _add_location(uow_factory, b['user_id'], b['team_id'], ReadRelease.REGISTERED, hidden, type_id)
    childless = await _add_location(uow_factory, a['user_id'], a['team_id'], ReadRelease.REGISTERED, country, type_id)
    hidden_only_child = await _add_location(uow_factory, b['user_id'], team_c, ReadRelease.PRIVATE, childless, type_id)
    hidden_in_other_country = await _add_location(uow_factory, b['user_id'], team_c, ReadRelease.PRIVATE, other_country, type_id)
    return {
        'user_a': a['user_id'], 'team_a': a['team_id'],
        'user_b': b['user_id'], 'team_b': b['team_id'], 'team_c': team_c,
        'user_d': user_d,
        'type_id': type_id,
        'country': country, 'parent': parent, 'hidden': hidden, 'shared': shared,
        'childless': childless, 'hidden_only_child': hidden_only_child,
        'other_country': other_country, 'hidden_in_other_country': hidden_in_other_country
    }


@pytest.mark.asyncio(loop_scope="session")
async def test_removing_a_location_with_only_hidden_children_is_refused(uow_factory, integrity_context):
    c = integrity_context
    async with uow_factory.get_uow(user_id=c['user_a']) as uow:
        location_tree = await uow.repositories.location_trees.get(location_id=c['childless'])
        with pytest.raises(IllegalOperationError):
            location_tree.remove_location(c['childless'])
    assert await _parents(uow_factory, c['hidden_only_child']) == [c['childless']]


@pytest.mark.asyncio(loop_scope="session")
async def test_removing_a_location_tree_root_with_hidden_members_is_refused(uow_factory, integrity_context):
    c = integrity_context
    async with uow_factory.get_uow(user_id=c['user_a']) as uow:
        location_tree = await uow.repositories.location_trees.get(location_id=c['other_country'])
        with pytest.raises(ProtectedNodeError):
            await uow.repositories.location_trees.remove(location_tree)
    assert await _parents(uow_factory, c['hidden_in_other_country']) == [c['other_country']]


@pytest.mark.asyncio(loop_scope="session")
async def test_moving_a_location_away_from_a_hidden_parent_is_refused(uow_factory, integrity_context):
    c = integrity_context
    async with uow_factory.get_uow(user_id=c['user_d']) as uow:
        location_tree = await uow.repositories.location_trees.get(location_id=c['shared'])
        location_tree.change_source(node_id=c['shared'], parent_id=c['parent'])
        with pytest.raises(UnauthorisedOperationError):
            await uow.commit()
    assert await _parents(uow_factory, c['shared']) == [c['hidden']]


@pytest.mark.asyncio(loop_scope="session")
async def test_attaching_under_a_hidden_parent_is_refused(uow_factory, integrity_context):
    c = integrity_context
    async with uow_factory.get_uow(user_id=c['user_d'], write_team=c['team_b']) as uow:
        location_tree = await uow.repositories.location_trees.get(location_id=c['shared'])
        location_tree.add_location(LocationInput(name=text.new_text(10), type=c['type_id']), parent_id=c['hidden'])
        with pytest.raises(UnauthorisedOperationError):
            await uow.commit()
    # but a readable parent is fine
    await _add_location(uow_factory, c['user_d'], c['team_b'], ReadRelease.PRIVATE, c['shared'], c['type_id'])


@pytest.mark.asyncio(loop_scope="session")
async def test_moving_a_location_keeps_a_single_parent(uow_factory, integrity_context):
    c = integrity_context
    # B reads every location here and curates "shared"
    async with uow_factory.get_uow(user_id=c['user_b']) as uow:
        location_tree = await uow.repositories.location_trees.get(location_id=c['shared'])
        location_tree.change_source(node_id=c['shared'], parent_id=c['parent'])
        await uow.commit()
    assert await _parents(uow_factory, c['shared']) == [c['parent']]
