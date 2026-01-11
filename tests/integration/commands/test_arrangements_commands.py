import pytest

from src.breedgraph.domain.model.ontology import OntologyEntryLabel
from src.breedgraph.domain.commands.arrangements import CreateLayout
from src.breedgraph.domain.model.controls import ReadRelease

@pytest.mark.usefixtures("session_database")
@pytest.mark.asyncio(scope="session")
async def test_add_layout_command_simple(
        bus,
        first_account_with_all_affiliations,
        basic_ontology,
        basic_region,
        lorem_text_generator
):
    async with bus.uow.get_uow(user_id=first_account_with_all_affiliations.user.id) as uow:

        named_layout_type = await uow.ontology.get_entry(name="Named", label=OntologyEntryLabel.LAYOUT_TYPE)
        location_type = await uow.ontology.get_entry(name="Field", label=OntologyEntryLabel.LOCATION_TYPE)
        location = next(basic_region.yield_locations_by_type(location_type.id))
        first_layout_command = CreateLayout(
            agent_id = first_account_with_all_affiliations.user.id,
            name = lorem_text_generator.new_text(),
            type_id = named_layout_type.id,
            location_id= location.id,
            axes = ["Sub-Field Section"],
            parent = None,
            position = None
        )
    await bus.handle(first_layout_command)
    async with bus.uow.get_uow(user_id=first_account_with_all_affiliations.user.id) as uow:
        async for arrangement in uow.repositories.arrangements.get_all(location_id = location.id):
            if first_layout_command.name in [i.name for i in arrangement.entries.values()]:
                break
            else:
                raise ValueError("First layout not found")

@pytest.mark.usefixtures("session_database")
@pytest.mark.asyncio(scope="session")
async def test_add_layout_command_nested(
        bus,
        first_account_with_all_affiliations,
        basic_ontology,
        basic_region,
        lorem_text_generator
):
    async with bus.uow.get_uow(user_id=first_account_with_all_affiliations.user.id) as uow:
        location_type = await uow.ontology.get_entry(name="Field", label=OntologyEntryLabel.LOCATION_TYPE)
        location = next(basic_region.yield_locations_by_type(location_type.id))

        async for arrangement in uow.repositories.arrangements.get_all(location_id=location.id):
            break
        else:
            raise ValueError("Arrangement not found")

        grid_layout_type = await uow.ontology.get_entry(name="Grid", label=OntologyEntryLabel.LAYOUT_TYPE)
        second_layout_command = CreateLayout(
            agent_id= first_account_with_all_affiliations.user.id,
            name = lorem_text_generator.new_text(),
            type_id = grid_layout_type.id,
            location_id= location.id,
            axes = ["x", "y"],
            parent = arrangement.get_root_id(),
            position = [1]
        )

    await bus.handle(second_layout_command)
    async with bus.uow.get_uow(user_id=first_account_with_all_affiliations.user.id) as uow:
        async for arrangement in uow.repositories.arrangements.get_all(location_id = location.id):
            layout_found = False
            for layout_id, layout in arrangement.get_sinks(arrangement.get_root_id()).items():
                if layout.name == second_layout_command.name:
                    layout_found = True
                    position = arrangement.get_source_edges(layout_id)[arrangement.get_root_id()]['position']
                    assert position == second_layout_command.position
                    break
            if layout_found:
                break
        else:
            raise ValueError("Second layout not found")