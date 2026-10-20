"""
Links to and from germplasm need read access to what they link to (docs/read-access.md rule 10): a unit to its
germplasm, and a germplasm entry to its origin location. Removing a link needs none.
"""
import pytest

from breedgraph.custom_exceptions import NoResultFoundError
from breedgraph.domain.commands.germplasm import CreateGermplasm, UpdateGermplasm
from breedgraph.domain.commands.unit_graphs import CreateUnit, UpdateUnit

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
