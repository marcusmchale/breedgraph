"""
Curate access to programs, trials and studies, which have controls of their own (docs/control-transfer.md): editing or
removing one needs curate access to it alone, and adding a trial or a study needs it to the program or trial it is
added to. Writes are stamped on what changed. So a study given to another team is that team's to edit and remove, and
no longer the trial team's.
"""
import pytest
import pytest_asyncio

from breedgraph.custom_exceptions import UnauthorisedOperationError
from breedgraph.domain.commands.programs import CreateStudy, UpdateStudy, DeleteStudy, CreateTrial, UpdateTrial, DeleteTrial
from breedgraph.domain.model.control_transfers import ControlledEntity
from breedgraph.domain.model.controls import ControlledModelLabel
from breedgraph.domain.model.programs import StudyInput

from tests.breedgraph.scenarios.account_builder import AccountBuilder
from tests.breedgraph.scenarios.program_builder import ProgramBuilder

TRIAL, STUDY = ControlledModelLabel.TRIAL, ControlledModelLabel.STUDY


@pytest_asyncio.fixture(loop_scope="session")
async def given_study(uow_factory):
    """A program, trial and study made by the trial team, the study then given to the study team"""
    trial_team = await AccountBuilder(uow_factory=uow_factory).account_with_affiliations()
    study_team = await AccountBuilder(uow_factory=uow_factory).account_with_affiliations()
    async with uow_factory.get_uow(user_id=trial_team['user_id'], write_team=trial_team['team_id']) as uow:
        program = await uow.repositories.programs.create(ProgramBuilder.program_input())
        program.add_trial(ProgramBuilder.trial_input())
        await uow.repositories.programs.update_seen()
        (trial_id,) = program.trials
        program.add_study(trial_id=trial_id, study=StudyInput(name='Given study'))
        await uow.repositories.programs.update_seen()
        (study_id,) = program.get_trial(trial_id).studies
        await uow.commit()

    async with uow_factory.get_uow(user_id=trial_team['user_id']) as uow:
        transfer = await uow.controls.offer_transfer(
            entities=[ControlledEntity(label=STUDY, id=study_id)],
            from_teams={trial_team['team_id']},
            recipient_team=study_team['team_id']
        )
        await uow.commit()
    async with uow_factory.get_uow(user_id=study_team['user_id']) as uow:
        await uow.controls.accept_transfer(transfer.id, to_teams={study_team['team_id']})
        await uow.commit()
    return {
        'trial_team': trial_team, 'study_team': study_team,
        'program_id': program.id, 'trial_id': trial_id, 'study_id': study_id
    }


async def read_program(uow_factory, given_study):
    async with uow_factory.get_uow(user_id=given_study['trial_team']['user_id']) as uow:
        return await uow.repositories.programs.get(program_id=given_study['program_id'])


async def writers(uow_factory, label: ControlledModelLabel, model_id: int) -> set[int]:
    async with uow_factory.get_uow() as uow:
        return {stamp.user for stamp in (await uow.controls.get_controller(label, model_id)).writes}


@pytest.mark.asyncio(loop_scope="session")
async def test_a_study_given_to_another_team_is_theirs_to_edit(bus, uow_factory, given_study):
    study_team, trial_team = given_study['study_team'], given_study['trial_team']
    await bus.handle(UpdateStudy(agent_id=study_team['user_id'], study_id=given_study['study_id'], name='Renamed by its team'))
    assert (await read_program(uow_factory, given_study)).get_study(given_study['study_id']).name == 'Renamed by its team'
    # the write is stamped on the study, not on the trial holding it
    assert study_team['user_id'] in await writers(uow_factory, STUDY, given_study['study_id'])
    assert study_team['user_id'] not in await writers(uow_factory, TRIAL, given_study['trial_id'])

    with pytest.raises(UnauthorisedOperationError, match="Editing requires curate permission"):
        await bus.handle(UpdateStudy(agent_id=trial_team['user_id'], study_id=given_study['study_id'], name='Renamed by the trial team'))
    assert (await read_program(uow_factory, given_study)).get_study(given_study['study_id']).name == 'Renamed by its team'


@pytest.mark.asyncio(loop_scope="session")
async def test_a_trial_is_its_teams_to_edit_and_to_add_studies_to(bus, uow_factory, given_study):
    study_team, trial_team = given_study['study_team'], given_study['trial_team']
    await bus.handle(UpdateTrial(agent_id=trial_team['user_id'], trial_id=given_study['trial_id'], name='Renamed trial'))
    assert (await read_program(uow_factory, given_study)).get_trial(given_study['trial_id']).name == 'Renamed trial'

    with pytest.raises(UnauthorisedOperationError, match="Editing requires curate permission"):
        await bus.handle(UpdateTrial(agent_id=study_team['user_id'], trial_id=given_study['trial_id'], name='Renamed by the study team'))
    with pytest.raises(UnauthorisedOperationError, match="Editing requires curate permission"):
        await bus.handle(CreateStudy(
            agent_id=study_team['user_id'], write_team=study_team['team_id'], trial_id=given_study['trial_id'], name='Another study'
        ))
    assert list((await read_program(uow_factory, given_study)).get_trial(given_study['trial_id']).studies) == [given_study['study_id']]


@pytest.mark.asyncio(loop_scope="session")
async def test_a_study_is_removed_by_its_curators_alone(bus, uow_factory, given_study):
    with pytest.raises(UnauthorisedOperationError, match="Removal requires curate permission"):
        await bus.handle(DeleteStudy(agent_id=given_study['trial_team']['user_id'], study_id=given_study['study_id']))
    assert (await read_program(uow_factory, given_study)).get_study(given_study['study_id']) is not None

    await bus.handle(DeleteStudy(agent_id=given_study['study_team']['user_id'], study_id=given_study['study_id']))
    assert (await read_program(uow_factory, given_study)).get_study(given_study['study_id']) is None


@pytest.mark.asyncio(loop_scope="session")
async def test_a_trial_without_studies_is_deleted_by_its_curators(bus, uow_factory, given_study):
    trial_team = given_study['trial_team']
    await bus.handle(CreateTrial(
        agent_id=trial_team['user_id'], write_team=trial_team['team_id'], program_id=given_study['program_id'], name='Empty trial'
    ))
    program = await read_program(uow_factory, given_study)
    (trial_id,) = [trial.id for trial in program.trials.values() if trial.name == 'Empty trial']

    with pytest.raises(UnauthorisedOperationError, match="Removal requires curate permission"):
        await bus.handle(DeleteTrial(agent_id=given_study['study_team']['user_id'], trial_id=trial_id))
    await bus.handle(DeleteTrial(agent_id=trial_team['user_id'], trial_id=trial_id))
    assert (await read_program(uow_factory, given_study)).get_trial(trial_id) is None
