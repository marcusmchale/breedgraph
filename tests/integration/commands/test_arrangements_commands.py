import pytest

from src.breedgraph.domain.commands.arrangements import CreateLayout

@pytest.mark.asyncio(loop_scope="session")
async def test_add_layout_command(
        bus,
        uow_factory, #
        lorem_text_generator,
        layout_build_context
):
    user_id = layout_build_context['user_id']
    location_id = layout_build_context['location_id']
    type_id = layout_build_context['ontology_layout_named']
    first_layout_command = CreateLayout(
        agent_id = user_id,
        name = lorem_text_generator.new_text(),
        type_id = type_id,
        location_id= location_id,
        axes = ["Section"],
        parent = None,
        position = None
    )
    await bus.handle(first_layout_command)

    async with uow_factory.get_uow(user_id=user_id) as uow:
        async for arrangement in uow.repositories.arrangements.get_all(location_id = location_id):
            if first_layout_command.name in [i.name for i in arrangement.entries.values()]:
                break
            else:
                raise ValueError("First layout not found")

@pytest.mark.asyncio(loop_scope="session")
async def test_add_layout_command_nested(
        bus,
        uow_factory,
        lorem_text_generator,
        layout_build_context
):
    user_id = layout_build_context['user_id']
    location_id = layout_build_context['location_id']
    type_id = layout_build_context['ontology_layout_grid']
    async with uow_factory.get_uow(user_id=user_id) as uow:
        async for arrangement in uow.repositories.arrangements.get_all(location_id=location_id):
            break
        else:
            raise ValueError("Arrangement not found")

        second_layout_command = CreateLayout(
            agent_id=user_id,
            name = lorem_text_generator.new_text(),
            type_id = type_id,
            location_id= location_id,
            axes = ["x", "y"],
            parent = arrangement.get_root_id(),
            position = [1]
        )

    await bus.handle(second_layout_command)

    async with uow_factory.get_uow(user_id=user_id) as uow:
        async for arrangement in uow.repositories.arrangements.get_all(location_id = location_id):
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