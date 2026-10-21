"""
Links to and from germplasm need read access to what they link to (docs/read-access.md rule 10): a unit to its
germplasm, and a germplasm entry to its origin location and to the unit it came from. Removing a link needs none.
A unit that germplasm came from is kept, as germplasm that units are of is.
"""
import pytest

from breedgraph.custom_exceptions import NoResultFoundError, ProtectedNodeError
from breedgraph.domain.commands.germplasm import CreateGermplasm, UpdateGermplasm, DeleteGermplasm
from breedgraph.domain.commands.unit_graphs import CreateUnit, UpdateUnit, DeleteUnit

from tests.breedgraph.scenarios.account_builder import AccountBuilder
from tests.breedgraph.scenarios.germplasm_builder import GermplasmBuilder
from tests.breedgraph.scenarios.location_tree_builder import LocationTreeBuilder
from tests.breedgraph.scenarios.unit_graph_builder import UnitGraphBuilder


@pytest.mark.asyncio(loop_scope="session")
async def test_linking_germplasm_or_an_origin_needs_read_access(bus, uow_factory, state_store, unit_graph_build_context):
    context = unit_graph_build_context
    user_id, team_id, location_id = context['user_id'], context['team_id'], context['location_id']
    germplasm_builder = GermplasmBuilder(uow_factory=uow_factory)
    germplasm_id = await germplasm_builder.germplasm(user_id=user_id, team_id=team_id)

    # another team's private germplasm and field, which the user cannot read
    other = await AccountBuilder(uow_factory=uow_factory).account_with_affiliations()
    hidden_germplasm_id = await germplasm_builder.germplasm(user_id=other['user_id'], team_id=other['team_id'])
    hidden_location_id = (await LocationTreeBuilder(uow_factory, state_store).location_tree(
        user_id=other['user_id'],
        team_id=other['team_id'],
        ontology_location_state=context['ontology_location_state'],
        ontology_location_field=context['ontology_location_field'],
        ontology_location_lab=context['ontology_location_lab']
    ))['location_field_id']

    # a unit's germplasm
    with pytest.raises(NoResultFoundError):
        await bus.handle(CreateUnit(
            agent_id=user_id, write_team=team_id, location_id=location_id, germplasm_id=hidden_germplasm_id
        ))
    unit_id = await UnitGraphBuilder(uow_factory=uow_factory).unit(user_id=user_id, team_id=team_id)
    with pytest.raises(NoResultFoundError):
        await bus.handle(UpdateUnit(agent_id=user_id, unit_id=unit_id, germplasm_id=hidden_germplasm_id))
    await bus.handle(UpdateUnit(agent_id=user_id, unit_id=unit_id, germplasm_id=germplasm_id))
    await bus.handle(UpdateUnit(agent_id=user_id, unit_id=unit_id, germplasm_id=None))

    # a germplasm entry's origin
    with pytest.raises(NoResultFoundError):
        await bus.handle(CreateGermplasm(
            agent_id=user_id, write_team=team_id, name=GermplasmBuilder.germplasm_input().name, origin_id=hidden_location_id
        ))
    with pytest.raises(NoResultFoundError):
        await bus.handle(UpdateGermplasm(agent_id=user_id, germplasm_id=germplasm_id, origin_id=hidden_location_id))
    await bus.handle(UpdateGermplasm(agent_id=user_id, germplasm_id=germplasm_id, origin_id=location_id))
    await bus.handle(UpdateGermplasm(agent_id=user_id, germplasm_id=germplasm_id, origin_id=None))

    async with uow_factory.get_uow(user_id=user_id) as uow:
        assert (await uow.repositories.unit_graphs.get(unit_id=unit_id)).get_unit(unit_id).germplasm is None
        assert (await uow.germplasm.get_entry(germplasm_id)).origin is None


async def entry_named(uow_factory, user_id: int, name: str):
    async with uow_factory.get_uow(user_id=user_id) as uow:
        (entry,) = [entry async for entry in uow.germplasm.get_entries(names=[name])]
        return entry


@pytest.mark.asyncio(loop_scope="session")
async def test_the_unit_germplasm_came_from_needs_read_access(bus, uow_factory, unit_graph_build_context):
    context = unit_graph_build_context
    user_id, team_id = context['user_id'], context['team_id']
    unit_builder = UnitGraphBuilder(uow_factory=uow_factory)
    unit_id = await unit_builder.unit(user_id=user_id, team_id=team_id)
    # another team's private unit, which the user cannot read
    other = await AccountBuilder(uow_factory=uow_factory).account_with_affiliations()
    hidden_unit_id = await unit_builder.unit(user_id=other['user_id'], team_id=other['team_id'])

    name = GermplasmBuilder.germplasm_input().name
    with pytest.raises(NoResultFoundError):
        await bus.handle(CreateGermplasm(agent_id=user_id, write_team=team_id, name=name, unit_id=hidden_unit_id))
    await bus.handle(CreateGermplasm(agent_id=user_id, write_team=team_id, name=name, unit_id=unit_id))
    entry = await entry_named(uow_factory, user_id, name)
    assert entry.unit == unit_id

    with pytest.raises(NoResultFoundError):
        await bus.handle(UpdateGermplasm(agent_id=user_id, germplasm_id=entry.id, unit_id=hidden_unit_id))
    # omitted, the unit is kept
    await bus.handle(UpdateGermplasm(agent_id=user_id, germplasm_id=entry.id, description='Selected from the unit'))
    assert (await entry_named(uow_factory, user_id, name)).unit == unit_id
    await bus.handle(UpdateGermplasm(agent_id=user_id, germplasm_id=entry.id, unit_id=None))
    assert (await entry_named(uow_factory, user_id, name)).unit is None
    await bus.handle(UpdateGermplasm(agent_id=user_id, germplasm_id=entry.id, unit_id=unit_id))
    assert (await entry_named(uow_factory, user_id, name)).unit == unit_id


@pytest.mark.asyncio(loop_scope="session")
async def test_a_unit_germplasm_came_from_is_not_deleted(bus, uow_factory, unit_graph_build_context):
    context = unit_graph_build_context
    user_id, team_id = context['user_id'], context['team_id']
    # a tree in a field, the unit a selection came from
    root_id = await UnitGraphBuilder(uow_factory=uow_factory).unit(user_id=user_id, team_id=team_id)
    tree = UnitGraphBuilder.unit_input()
    async with uow_factory.get_uow(user_id=user_id, write_team=team_id) as uow:
        unit_graph = await uow.repositories.unit_graphs.get(unit_id=root_id)
        unit_graph.add_unit(tree, parents=[root_id])
        await uow.commit()
    async with uow_factory.get_uow(user_id=user_id) as uow:
        unit_graph = await uow.repositories.unit_graphs.get(unit_id=root_id)
        (tree_id,) = [unit.id for unit in unit_graph.entries.values() if unit.name == tree.name]
    name = GermplasmBuilder.germplasm_input().name
    await bus.handle(CreateGermplasm(agent_id=user_id, write_team=team_id, name=name, unit_id=tree_id))

    with pytest.raises(ProtectedNodeError):
        await bus.handle(DeleteUnit(agent_id=user_id, unit_id=tree_id))
    # one who can't read the unit is told it was not found, and learns nothing of the germplasm
    other = await AccountBuilder(uow_factory=uow_factory).account_with_affiliations()
    with pytest.raises(NoResultFoundError):
        await bus.handle(DeleteUnit(agent_id=other['user_id'], unit_id=tree_id))

    # deleting the germplasm removes its link, and then the unit can go
    await bus.handle(DeleteGermplasm(agent_id=user_id, germplasm_id=(await entry_named(uow_factory, user_id, name)).id))
    await bus.handle(DeleteUnit(agent_id=user_id, unit_id=tree_id))
    async with uow_factory.get_uow(user_id=user_id) as uow:
        assert not (await uow.repositories.unit_graphs.get(unit_id=root_id)).has_unit(tree_id)
