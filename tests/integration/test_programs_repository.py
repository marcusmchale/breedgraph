import pytest, pytest_asyncio
from src.breedgraph.domain.model.programs import (
    ProgramInput, ProgramStored,
    TrialInput, TrialStored,
    StudyInput, StudyStored
)

from src.breedgraph.adapters.repositories.programs import Neo4jProgramsRepository
from src.breedgraph.custom_exceptions import NoResultFoundError, UnauthorisedOperationError

@pytest.mark.asyncio(scope="session")
async def test_create_and_get(
        programs_repo
):
    program_input = ProgramInput(name='BOLERO')
    stored_program = await programs_repo.create(program_input)
    retrieved_program: ProgramStored = await programs_repo.get(program_id = stored_program.id)
    assert stored_program.name == retrieved_program.name
    async for program in programs_repo.get_all():
        if program.name == program_input.name:
            break
    else:
        raise NoResultFoundError("Couldn't find created program by get all")

@pytest.mark.asyncio(scope="session")
async def test_extend_program_with_trial(
        programs_repo,
        lorem_text_generator
):
    program = await programs_repo.get()
    new_trial = TrialInput(name='New Trial')
    program.add_trial(new_trial)
    await programs_repo.update_seen()
    assert list(program.trials.keys())[0] > 0

@pytest.mark.asyncio(scope="session")
async def test_extend_trial_with_study(
        programs_repo,
        lorem_text_generator
):
    program = await programs_repo.get()
    new_study = StudyInput(name='New Study')
    program.trials[1].add_study(new_study)
    await programs_repo.update_seen()
    assert list(list(program.trials.values())[0].studies.keys())[0] > 0

@pytest.mark.asyncio(scope="session")
async def test_edit_study(
        programs_repo,
        lorem_text_generator,
        neo4j_tx,
        stored_account,
        stored_organisation
):
    program = await programs_repo.get()
    study = program.trials[1].studies[1]
    study.name = 'New Study Name'
    await programs_repo.update_seen()

    new_repo = Neo4jProgramsRepository(
        neo4j_tx,
        user_id=stored_account.user.id,
        read_teams=[stored_organisation.root.id]
    )
    retrieved = await new_repo.get()
    study = retrieved.trials[1].studies[1]
    assert study.name == 'New Study Name'

@pytest.mark.asyncio(scope="session")
async def test_edit_trial(
        programs_repo,
        lorem_text_generator,
        neo4j_tx,
        stored_account,
        stored_organisation
):
    program = await programs_repo.get()
    trial = program.trials[1]
    trial.name = 'New Trial Name'
    await programs_repo.update_seen()

    new_repo = Neo4jProgramsRepository(
        neo4j_tx,
        user_id=stored_account.user.id,
        read_teams=[stored_organisation.root.id]
    )
    retrieved = await new_repo.get()
    trial = retrieved.trials[1]
    assert trial.name == 'New Trial Name'

@pytest.mark.asyncio(scope="session")
async def test_edit_program(
        programs_repo,
        lorem_text_generator,
        neo4j_tx,
        stored_account,
        stored_organisation
):
    program = await programs_repo.get()
    program.name = 'New Program Name'
    await programs_repo.update_seen()

    new_repo = Neo4jProgramsRepository(
        neo4j_tx,
        user_id=stored_account.user.id,
        read_teams=[stored_organisation.root.id]
    )
    retrieved = await new_repo.get()
    assert retrieved.name == 'New Program Name'