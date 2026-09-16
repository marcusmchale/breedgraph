import pytest

from breedgraph.custom_exceptions import NoResultFoundError
from breedgraph.domain.model import GroupingScope


from tests.breedgraph.scenarios.program_builder import ProgramBuilder


@pytest.mark.asyncio(loop_scope="session")
async def test_create(
        uow_factory,
        program_build_context
):
    user_id = program_build_context['user_id']
    replicate_type = program_build_context['ontology_record_group_replicate']
    batch_type = program_build_context['ontology_record_group_batch']
    program_input = ProgramBuilder.program_input()
    trial_input = ProgramBuilder.trial_input()
    study_input = ProgramBuilder.study_input(replicate_type=replicate_type, batch_type=batch_type)

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

@pytest.mark.asyncio(loop_scope="session")
async def test_update_study(uow_factory, program_build_context):
    user_id: int = program_build_context['user_id']
    replicate_type: int = program_build_context['ontology_record_group_replicate']
    batch_type: int = program_build_context['ontology_record_group_batch']
    program_input = ProgramBuilder.program_input()
    trial_input = ProgramBuilder.trial_input()
    study_input = ProgramBuilder.study_input(
        replicate_type=replicate_type, batch_type=batch_type
    )
    # create a trial
    async with uow_factory.get_uow(user_id=user_id) as uow:
        program = await uow.repositories.programs.create(program_input)
        program.add_trial(trial_input)
        await uow.commit()

    # add a study
    async with uow_factory.get_uow(user_id=user_id) as uow:
        program = await uow.repositories.programs.get(program_id=program.id)
        trial_id = list(program.trials.keys())[0]
        program.add_study(trial_id=trial_id, study=study_input)
        await uow.commit()

    # ensure study was added
    async with uow_factory.get_uow(user_id=user_id) as uow:
        program = await uow.repositories.programs.get(program_id=program.id)
        trial_id = list(program.trials.keys())[0]
        study_id = list(program.trials[trial_id].studies.keys())[0]
        study = program.get_study(study_id=study_id)
        # now change some details
        study.name = 'New Name For Study'
        grouping = study.get_grouping(name="Study Scoped batch")
        grouping.name = "Study Scoped Run"
        await uow.commit()

    async with uow_factory.get_uow(user_id=user_id) as uow:
        program = await uow.repositories.programs.get(program_id=program.id)
        study = program.get_study(study_id=study_id)
        # verify the changed details
        assert study.name == 'New Name For Study'
        grouping = study.get_grouping(name="Study Scoped Run")
        assert grouping


