import pytest

from breedgraph.custom_exceptions import NoResultFoundError

from tests.scenarios.program_builder import ProgramBuilder

@pytest.mark.asyncio(loop_scope="session")
async def test_create(
        uow_factory,
        program_build_context
):
    user_id = program_build_context['user_id']
    program_input = ProgramBuilder.program_input()
    trial_input = ProgramBuilder.trial_input()
    study_input = ProgramBuilder.study_input()

    async with uow_factory.get_uow(user_id=user_id) as uow:
        program = await uow.repositories.programs.create(program_input)
        program.add_trial(trial_input)
        await uow.commit()

    async with uow_factory.get_uow(user_id=user_id) as uow:
        program = await uow.repositories.programs.get(program_id=program.id)
        trial_id = list(program.trials.keys())[0]
        program.add_study(trial_id=trial_id, study=study_input)
        await uow.commit()

    trial_id = list(program.trials.keys())[0]
    study_id = list(program.get_trial(trial_id).studies.keys())[0]
    async with uow_factory.get_uow(user_id=user_id) as uow:
        async for program in uow.repositories.programs.get_all():
            if program.name == program_input.name:
                trial = program.get_trial(trial_id=trial_id)
                assert trial.name == trial_input.name
                study = program.get_study(study_id=study_id)
                assert study.name == study_input.name
                break
        else:
            raise NoResultFoundError("Couldn't find created program by get all")
