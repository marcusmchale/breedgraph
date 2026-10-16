import pytest

from breedgraph.custom_exceptions import IllegalOperationError, NoResultFoundError
from breedgraph.domain.commands.germplasm import CreateGermplasm
from breedgraph.domain.commands.programs import CreateProgram, UpdateProgram, CreateTrial, CreateStudy, UpdateStudy
from breedgraph.domain.commands.references import DeleteReferences
from breedgraph.domain.model.programs import StudyInput

from tests.breedgraph.scenarios.account_builder import AccountBuilder
from tests.breedgraph.scenarios.program_builder import ProgramBuilder
from tests.breedgraph.scenarios.reference_builder import ReferenceBuilder


async def create_legal_reference(uow_factory, context) -> int:
    async with uow_factory.get_uow(user_id=context['user_id'], write_team=context['team_id']) as uow:
        reference = await uow.repositories.references.create(ReferenceBuilder.legal_reference_input())
        await uow.commit()
        return reference.id


async def reference_exists(uow_factory, context, reference_id: int) -> bool:
    async with uow_factory.get_uow(user_id=context['user_id']) as uow:
        return [reference.id async for reference in uow.repositories.references.get_all(reference_ids=[reference_id])] == [reference_id]


@pytest.mark.asyncio(loop_scope="session")
async def test_unused_reference_is_deleted(bus, uow_factory, program_build_context):
    reference_id = await create_legal_reference(uow_factory, program_build_context)
    await bus.handle(DeleteReferences(agent_id=program_build_context['user_id'], reference_ids=[reference_id]))
    assert not await reference_exists(uow_factory, program_build_context, reference_id)


@pytest.mark.asyncio(loop_scope="session")
async def test_licence_in_use_is_protected(bus, uow_factory, program_build_context):
    context = program_build_context
    licence_id = await create_legal_reference(uow_factory, context)
    async with uow_factory.get_uow(user_id=context['user_id'], write_team=context['team_id']) as uow:
        program = await uow.repositories.programs.create(ProgramBuilder.program_input())
        program.add_trial(ProgramBuilder.trial_input())
        await uow.repositories.programs.update_seen()
        trial_id = list(program.trials.keys())[0]
        program.add_study(trial_id=trial_id, study=StudyInput(name=ProgramBuilder.program_input().name, licence_id=licence_id))
        await uow.commit()

    with pytest.raises(IllegalOperationError):
        await bus.handle(DeleteReferences(agent_id=context['user_id'], reference_ids=[licence_id]))
    assert await reference_exists(uow_factory, context, licence_id)


@pytest.mark.asyncio(loop_scope="session")
async def test_citing_an_unreadable_reference_is_refused(bus, uow_factory, program_build_context):
    context = program_build_context
    other = await AccountBuilder(uow_factory=uow_factory).account_with_affiliations()
    hidden_id = await create_legal_reference(uow_factory, other)
    readable_id = await create_legal_reference(uow_factory, context)
    user_id, team_id = context['user_id'], context['team_id']

    with pytest.raises(NoResultFoundError):
        await bus.handle(CreateProgram(agent_id=user_id, write_team=team_id, name=ProgramBuilder.program_input().name, reference_ids=[hidden_id]))
    with pytest.raises(NoResultFoundError):
        await bus.handle(CreateGermplasm(agent_id=user_id, write_team=team_id, name=ProgramBuilder.program_input().name, reference_ids=[hidden_id]))

    name = ProgramBuilder.program_input().name
    await bus.handle(CreateProgram(agent_id=user_id, write_team=team_id, name=name, reference_ids=[readable_id]))
    async with uow_factory.get_uow(user_id=user_id) as uow:
        program_id = (await uow.repositories.programs.get(name=name)).id
    with pytest.raises(NoResultFoundError):
        await bus.handle(UpdateProgram(agent_id=user_id, program_id=program_id, reference_ids=[readable_id, hidden_id]))

    trial_name = ProgramBuilder.trial_input().name
    with pytest.raises(NoResultFoundError):
        await bus.handle(CreateTrial(agent_id=user_id, write_team=team_id, program_id=program_id, name=trial_name, reference_ids=[hidden_id]))
    await bus.handle(CreateTrial(agent_id=user_id, write_team=team_id, program_id=program_id, name=trial_name))
    async with uow_factory.get_uow(user_id=user_id) as uow:
        trial_id = list((await uow.repositories.programs.get(program_id=program_id)).trials.keys())[0]

    study_name = ProgramBuilder.trial_input().name
    with pytest.raises(NoResultFoundError):
        await bus.handle(CreateStudy(agent_id=user_id, write_team=team_id, trial_id=trial_id, name=study_name, licence_id=hidden_id))
    await bus.handle(CreateStudy(agent_id=user_id, write_team=team_id, trial_id=trial_id, name=study_name, licence_id=readable_id))
    async with uow_factory.get_uow(user_id=user_id) as uow:
        program = await uow.repositories.programs.get(program_id=program_id)
        study_id = list(program.get_trial(trial_id).studies.keys())[0]
    with pytest.raises(NoResultFoundError):
        await bus.handle(UpdateStudy(agent_id=user_id, study_id=study_id, licence_id=hidden_id))
    with pytest.raises(NoResultFoundError):
        await bus.handle(UpdateStudy(agent_id=user_id, study_id=study_id, reference_ids=[hidden_id]))
