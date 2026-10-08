import pytest
import pytest_asyncio

from breedgraph.custom_exceptions import IllegalOperationError
from breedgraph.domain.model.controls import ControlledModelLabel, ReadRelease

from tests.breedgraph.scenarios.account_builder import AccountBuilder
from tests.breedgraph.scenarios.germplasm_builder import GermplasmBuilder
from tests.breedgraph.scenarios.program_builder import ProgramBuilder


@pytest_asyncio.fixture(scope="module", loop_scope="session")
async def control_change_context(isolated_state, uow_factory) -> dict:
    account_builder = AccountBuilder(uow_factory=uow_factory)
    account_1 = await account_builder.account_with_affiliations()
    account_2 = await account_builder.account_with_affiliations()
    return {
        'user_id_1': account_1['user_id'],
        'team_id_1': account_1['team_id'],
        'user_id_2': account_2['user_id'],
        'team_id_2': account_2['team_id']
    }


async def create_program(uow_factory, user_id: int, team_id: int) -> int:
    async with uow_factory.get_uow(user_id=user_id, write_team=team_id) as uow:
        program = await uow.repositories.programs.create(ProgramBuilder.program_input())
        await uow.commit()
    return program.id


async def get_control_teams(uow_factory, user_id: int, label: ControlledModelLabel, model_id: int) -> set[int]:
    async with uow_factory.get_uow(user_id=user_id) as uow:
        controller = await uow.controls.get_controller(label, model_id)
    return controller.teams


@pytest.mark.asyncio(loop_scope="session")
async def test_add_and_end_controls(uow_factory, control_change_context):
    user_id_1 = control_change_context['user_id_1']
    team_id_1 = control_change_context['team_id_1']
    user_id_2 = control_change_context['user_id_2']
    team_id_2 = control_change_context['team_id_2']
    program_id = await create_program(uow_factory, user_id_1, team_id_1)

    # Only the first team can read the private program
    async with uow_factory.get_uow(user_id=user_id_2) as uow:
        program = await uow.repositories.programs.get(program_id=program_id)
        assert program.name == program._redacted_str

    async with uow_factory.get_uow(user_id=user_id_1) as uow:
        await uow.controls.add_controls(
            ControlledModelLabel.PROGRAM, [program_id], {team_id_2}, ReadRelease.PRIVATE
        )
        await uow.commit()

    assert await get_control_teams(uow_factory, user_id_1, ControlledModelLabel.PROGRAM, program_id) == {team_id_1, team_id_2}
    async with uow_factory.get_uow(user_id=user_id_2) as uow:
        program = await uow.repositories.programs.get(program_id=program_id)
        assert program.name != program._redacted_str

    async with uow_factory.get_uow(user_id=user_id_1) as uow:
        await uow.controls.end_controls(ControlledModelLabel.PROGRAM, [program_id], {team_id_1})
        await uow.commit()

    assert await get_control_teams(uow_factory, user_id_1, ControlledModelLabel.PROGRAM, program_id) == {team_id_2}
    async with uow_factory.get_uow(user_id=user_id_1) as uow:
        program = await uow.repositories.programs.get(program_id=program_id)
        assert program.name == program._redacted_str


@pytest.mark.asyncio(loop_scope="session")
async def test_ended_controls_are_kept_as_history(uow_factory, control_change_context):
    user_id_1 = control_change_context['user_id_1']
    team_id_1 = control_change_context['team_id_1']
    team_id_2 = control_change_context['team_id_2']
    program_id = await create_program(uow_factory, user_id_1, team_id_1)

    async with uow_factory.get_uow(user_id=user_id_1) as uow:
        await uow.controls.add_controls(
            ControlledModelLabel.PROGRAM, [program_id], {team_id_2}, ReadRelease.PRIVATE
        )
        await uow.controls.end_controls(ControlledModelLabel.PROGRAM, [program_id], {team_id_1})
        await uow.commit()

    async with uow_factory.get_uow(user_id=user_id_1) as uow:
        result = await uow.tx.run(
            "MATCH (:Team {id: $team_id})-[:CONTROLS]->(:TeamPrograms)-[:CONTROLS]->(control:Control)"
            "-[:CONTROLS]->(:Program {id: $program_id}) "
            "RETURN control.ended AS ended ORDER BY control.sequence",
            team_id=team_id_1,
            program_id=program_id
        )
        ended = [record['ended'] async for record in result]
    assert ended == [None, True]


@pytest.mark.asyncio(loop_scope="session")
async def test_ending_all_control_teams_is_refused(uow_factory, control_change_context):
    user_id_1 = control_change_context['user_id_1']
    team_id_1 = control_change_context['team_id_1']
    program_id = await create_program(uow_factory, user_id_1, team_id_1)

    async with uow_factory.get_uow(user_id=user_id_1) as uow:
        with pytest.raises(IllegalOperationError, match="At least one control team must remain"):
            await uow.controls.end_controls(ControlledModelLabel.PROGRAM, [program_id], {team_id_1})

    assert await get_control_teams(uow_factory, user_id_1, ControlledModelLabel.PROGRAM, program_id) == {team_id_1}


@pytest.mark.asyncio(loop_scope="session")
async def test_ending_a_team_without_control_is_refused(uow_factory, control_change_context):
    user_id_1 = control_change_context['user_id_1']
    team_id_1 = control_change_context['team_id_1']
    team_id_2 = control_change_context['team_id_2']
    program_id = await create_program(uow_factory, user_id_1, team_id_1)

    async with uow_factory.get_uow(user_id=user_id_1) as uow:
        with pytest.raises(IllegalOperationError, match="Teams do not control"):
            await uow.controls.end_controls(ControlledModelLabel.PROGRAM, [program_id], {team_id_2})


@pytest.mark.asyncio(loop_scope="session")
async def test_adding_a_current_control_team_is_refused(uow_factory, control_change_context):
    user_id_1 = control_change_context['user_id_1']
    team_id_1 = control_change_context['team_id_1']
    program_id = await create_program(uow_factory, user_id_1, team_id_1)

    async with uow_factory.get_uow(user_id=user_id_1) as uow:
        with pytest.raises(IllegalOperationError, match="Teams already control"):
            await uow.controls.add_controls(
                ControlledModelLabel.PROGRAM, [program_id], {team_id_1}, ReadRelease.PRIVATE
            )


@pytest.mark.asyncio(loop_scope="session")
async def test_ended_team_can_control_again(uow_factory, control_change_context):
    user_id_1 = control_change_context['user_id_1']
    team_id_1 = control_change_context['team_id_1']
    team_id_2 = control_change_context['team_id_2']
    program_id = await create_program(uow_factory, user_id_1, team_id_1)

    async with uow_factory.get_uow(user_id=user_id_1) as uow:
        await uow.controls.add_controls(
            ControlledModelLabel.PROGRAM, [program_id], {team_id_2}, ReadRelease.PRIVATE
        )
        await uow.controls.end_controls(ControlledModelLabel.PROGRAM, [program_id], {team_id_1})
        await uow.controls.add_controls(
            ControlledModelLabel.PROGRAM, [program_id], {team_id_1}, ReadRelease.PRIVATE
        )
        await uow.commit()

    assert await get_control_teams(uow_factory, user_id_1, ControlledModelLabel.PROGRAM, program_id) == {team_id_1, team_id_2}


@pytest.mark.asyncio(loop_scope="session")
async def test_germplasm_views_ignore_ended_controls(uow_factory, views_factory, control_change_context):
    user_id_1 = control_change_context['user_id_1']
    team_id_1 = control_change_context['team_id_1']
    team_id_2 = control_change_context['team_id_2']
    germplasm_id = await GermplasmBuilder(uow_factory).germplasm(user_id=user_id_1, team_id=team_id_1)

    async with views_factory.get_views(user_id=user_id_1) as views:
        [entry] = await views.germplasm.get_entries(entry_ids=[germplasm_id])
        assert entry.name != 'REDACTED'

    async with uow_factory.get_uow(user_id=user_id_1) as uow:
        await uow.controls.add_controls(
            ControlledModelLabel.GERMPLASM, [germplasm_id], {team_id_2}, ReadRelease.PRIVATE
        )
        await uow.controls.end_controls(ControlledModelLabel.GERMPLASM, [germplasm_id], {team_id_1})
        await uow.commit()

    async with views_factory.get_views(user_id=user_id_1) as views:
        [entry] = await views.germplasm.get_entries(entry_ids=[germplasm_id])
        assert entry.name == 'REDACTED'
