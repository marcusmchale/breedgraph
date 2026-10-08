import pytest

from breedgraph.custom_exceptions import IdentityExistsError
from breedgraph.domain.commands.programs import CreateProgram, UpdateProgram

from tests.breedgraph.scenarios.program_builder import ProgramBuilder


async def create_program(bus, uow_factory, context, name: str) -> int:
    await bus.handle(CreateProgram(agent_id=context['user_id'], write_team=context['team_id'], name=name))
    async with uow_factory.get_uow(user_id=context['user_id']) as uow:
        return (await uow.repositories.programs.get(name=name)).id


@pytest.mark.asyncio(loop_scope="session")
async def test_program_names_are_unique(bus, uow_factory, program_build_context):
    name = ProgramBuilder.program_input().name
    await create_program(bus, uow_factory, program_build_context, name)
    with pytest.raises(IdentityExistsError):
        await bus.handle(CreateProgram(
            agent_id=program_build_context['user_id'], write_team=program_build_context['team_id'], name=name.upper()
        ))


@pytest.mark.asyncio(loop_scope="session")
async def test_rename_to_existing_name_is_refused(bus, uow_factory, program_build_context):
    first_name = ProgramBuilder.program_input().name
    await create_program(bus, uow_factory, program_build_context, first_name)
    second_id = await create_program(bus, uow_factory, program_build_context, ProgramBuilder.program_input().name)
    with pytest.raises(IdentityExistsError):
        await bus.handle(UpdateProgram(agent_id=program_build_context['user_id'], program_id=second_id, name=first_name))
