import pytest

from breedgraph.custom_exceptions import IdentityExistsError
from breedgraph.domain.commands.programs import CreateProgram, UpdateProgram

from tests.breedgraph.scenarios.account_builder import AccountBuilder
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


@pytest.mark.asyncio(loop_scope="session")
async def test_programs_and_trials_credit_persons_with_roles(bus, uow_factory, program_build_context):
    from breedgraph.custom_exceptions import NoResultFoundError
    from breedgraph.domain.commands.programs import CreateTrial, UpdateTrial
    from breedgraph.domain.model.ontology import OntologyEntryLabel
    from tests.breedgraph.scenarios.person_builder import PersonBuilder

    context = program_build_context
    user_id, team_id = context['user_id'], context['team_id']
    person_id = await PersonBuilder(uow_factory=uow_factory).person(user_id=user_id, team_id=team_id)
    other = await AccountBuilder(uow_factory=uow_factory).account_with_affiliations()
    hidden_id = await PersonBuilder(uow_factory=uow_factory).person(user_id=other['user_id'], team_id=other['team_id'])
    async with uow_factory.get_uow(user_id=user_id) as uow:
        funding, administration = [
            (await uow.ontology.get_entry(name=name, label=OntologyEntryLabel.ROLE)).id
            for name in ('Funding acquisition', 'Project administration')
        ]
        country = (await uow.ontology.get_entry(name='Country', label=OntologyEntryLabel.LOCATION_TYPE)).id

    name = ProgramBuilder.program_input().name
    await bus.handle(CreateProgram(
        agent_id=user_id, write_team=team_id, name=name,
        contributions=[{'person_id': person_id, 'role_ids': [funding]}]
    ))
    async with uow_factory.get_uow(user_id=user_id) as uow:
        program = await uow.repositories.programs.get(name=name)
    assert [(c.person, c.roles) for c in program.contributions] == [(person_id, [funding])]

    await bus.handle(UpdateProgram(
        agent_id=user_id, program_id=program.id,
        contributions=[{'person_id': person_id, 'role_ids': [funding, administration]}]
    ))
    await bus.handle(CreateTrial(
        agent_id=user_id, write_team=team_id, program_id=program.id, name=ProgramBuilder.trial_input().name,
        contributions=[{'person_id': person_id}]
    ))
    async with uow_factory.get_uow(user_id=user_id) as uow:
        program = await uow.repositories.programs.get(program_id=program.id)
        trial = list(program.trials.values())[0]
    assert [(c.person, sorted(c.roles)) for c in program.contributions] == [(person_id, sorted([funding, administration]))]
    assert [(c.person, c.roles) for c in trial.contributions] == [(person_id, [])]

    # a Person the user cannot read, and an entry that is not a Role, are refused
    with pytest.raises(NoResultFoundError):
        await bus.handle(UpdateTrial(agent_id=user_id, trial_id=trial.id, contributions=[{'person_id': hidden_id}]))
    with pytest.raises(ValueError):
        await bus.handle(UpdateTrial(
            agent_id=user_id, trial_id=trial.id, contributions=[{'person_id': person_id, 'role_ids': [country]}]
        ))
