"""
Updates change only the fields given: one left out is unchanged, and null clears an optional one, as does an empty or
blank string for text (README, Updates)
"""
import pytest
import pytest_asyncio

from breedgraph.domain.commands.germplasm import UpdateGermplasm
from breedgraph.domain.commands.layout_trees import UpdateLayout
from breedgraph.domain.commands.location_trees import UpdateLocation
from breedgraph.domain.commands.ontologies import UpdateSubject
from breedgraph.domain.commands.people import UpdatePerson
from breedgraph.domain.commands.programs import UpdateProgram, UpdateTrial, UpdateStudy
from breedgraph.domain.commands.references import UpdateExternalReference
from breedgraph.domain.commands.team_trees import UpdateTeam
from breedgraph.domain.commands.unit_graphs import UpdateUnit
from breedgraph.domain.model.germplasm import Reproduction
from breedgraph.domain.model.layout_trees import LayoutInput
from breedgraph.domain.model.ontology import SubjectInput, VersionChange
from breedgraph.domain.model.references import ExternalReferenceInput

from tests.breedgraph.scenarios.account_builder import AccountBuilder
from tests.breedgraph.scenarios.germplasm_builder import GermplasmBuilder
from tests.breedgraph.scenarios.location_tree_builder import LocationTreeBuilder
from tests.breedgraph.scenarios.ontology_builder import OntologyBuilder
from tests.breedgraph.scenarios.person_builder import PersonBuilder
from tests.breedgraph.scenarios.program_builder import ProgramBuilder
from tests.breedgraph.scenarios.unit_graph_builder import UnitGraphBuilder


@pytest_asyncio.fixture(scope="module", loop_scope="session")
async def context(isolated_state, uow_factory, state_store) -> dict:
    account = await AccountBuilder(uow_factory=uow_factory).account_with_affiliations()
    user_id, team_id = account['user_id'], account['team_id']
    ontology_builder = OntologyBuilder(uow_factory=uow_factory)
    record_group_types = await ontology_builder.record_group_types(user_id=user_id)
    program = await ProgramBuilder(uow_factory=uow_factory).program_trial_study(
        user_id, team_id,
        replicate_type=record_group_types['ontology_record_group_replicate'],
        batch_type=record_group_types['ontology_record_group_batch']
    )
    location_types = await ontology_builder.location_types(user_id=user_id)
    locations = await LocationTreeBuilder(uow_factory=uow_factory, state_store=state_store).location_tree(
        user_id=user_id, team_id=team_id,
        ontology_location_state=location_types['ontology_location_state'],
        ontology_location_field=location_types['ontology_location_field'],
        ontology_location_lab=location_types['ontology_location_lab']
    )
    layout_types = await ontology_builder.layout_types(user_id=user_id)
    async with uow_factory.get_uow(user_id=user_id, write_team=team_id) as uow:
        layout_tree = await uow.repositories.layout_trees.create(LayoutInput(
            name="Clearing Benches", type=layout_types['ontology_layout_named'],
            location=locations['location_field_id'], axes=["Bench"]
        ))
        reference = await uow.repositories.references.create(ExternalReferenceInput(
            description="A data portal", url="https://example.org/data", external_id="EX-1"
        ))
        subject = await uow.ontology.create_entry(SubjectInput(
            name="Clearing Shoot", abbreviation="CS", synonyms=["Clearing Sprout"], description="A shoot"
        ))
        await uow.ontology.commit_version(version_change=VersionChange.PATCH)
        await uow.commit()
    return {
        **account, **program, **locations,
        'layout_id': layout_tree.root.id,
        'reference_id': reference.id,
        'subject_id': subject.id,
        'unit_id': await UnitGraphBuilder(uow_factory=uow_factory).unit(user_id=user_id, team_id=team_id),
        'germplasm_id': await GermplasmBuilder(uow_factory=uow_factory).germplasm(user_id=user_id, team_id=team_id),
        'person_id': await PersonBuilder(uow_factory=uow_factory).person(user_id=user_id, team_id=team_id),
    }


@pytest.mark.asyncio(loop_scope="session")
async def test_programs_trials_and_studies(bus, uow_factory, context):
    user_id = context['user_id']
    await bus.handle(UpdateProgram(agent_id=user_id, program_id=context['program_id'], fullname="Full", description="About"))
    await bus.handle(UpdateTrial(
        agent_id=user_id, trial_id=context['trial_id'], description="Trial", start="2024-01-01", end="2024-12-31"
    ))
    await bus.handle(UpdateStudy(agent_id=user_id, study_id=context['study_id'], practices="Pruned", description="Study"))

    await bus.handle(UpdateProgram(agent_id=user_id, program_id=context['program_id'], description=None))
    await bus.handle(UpdateTrial(agent_id=user_id, trial_id=context['trial_id'], start=None))
    await bus.handle(UpdateStudy(agent_id=user_id, study_id=context['study_id'], practices="  "))

    async with uow_factory.get_uow(user_id=user_id) as uow:
        program = await uow.repositories.programs.get(program_id=context['program_id'])
        trial, study = program.trials[context['trial_id']], program.get_study(context['study_id'])
        assert (program.fullname, program.description) == ("Full", None), "cleared by null; left out, unchanged"
        assert trial.start is None and trial.end is not None and trial.description == "Trial"
        assert (study.practices, study.description) == (None, "Study"), "a blank string clears text"


@pytest.mark.asyncio(loop_scope="session")
async def test_units_locations_and_layouts(bus, uow_factory, context):
    user_id = context['user_id']
    location_id, country_id = context['location_field_id'], context['location_country_id']
    await bus.handle(UpdateUnit(agent_id=user_id, unit_id=context['unit_id'], name="Tree", description="Tall"))
    await bus.handle(UpdateLocation(agent_id=user_id, location_id=location_id, code="F1", address="Lane", description="Flat"))
    await bus.handle(UpdateUnit(agent_id=user_id, unit_id=context['unit_id'], description=None))
    await bus.handle(UpdateLocation(agent_id=user_id, location_id=location_id, code="", address=None))
    await bus.handle(UpdateLayout(agent_id=user_id, layout_id=context['layout_id'], name=None))
    with pytest.raises(ValueError, match="A country keeps its code"):
        await bus.handle(UpdateLocation(agent_id=user_id, location_id=country_id, code=None))

    async with uow_factory.get_uow(user_id=user_id) as uow:
        unit = (await uow.repositories.unit_graphs.get(unit_id=context['unit_id'])).get_unit(context['unit_id'])
        location = (await uow.repositories.location_trees.get(location_id=location_id)).get_location(location_id)
        layout = (await uow.repositories.layout_trees.get(layout_id=context['layout_id'])).get_layout(context['layout_id'])
        country = (await uow.repositories.location_trees.get(location_id=country_id)).get_location(country_id)
        assert (unit.name, unit.description) == ("Tree", None)
        assert (location.code, location.address, location.description) == (None, None, "Flat")
        assert layout.name is None
        assert country.code


@pytest.mark.asyncio(loop_scope="session")
async def test_germplasm_people_teams_references_and_ontology(bus, uow_factory, context):
    user_id = context['user_id']
    await bus.handle(UpdateGermplasm(
        agent_id=user_id, germplasm_id=context['germplasm_id'], description="Clone", synonyms=["C1"],
        time="2020-05-01", reproduction=Reproduction.CLONAL
    ))
    await bus.handle(UpdatePerson(agent_id=user_id, person_id=context['person_id'], institution="University"))
    await bus.handle(UpdateTeam(agent_id=user_id, team_id=context['team_id'], fullname="The Team"))

    await bus.handle(UpdateGermplasm(
        agent_id=user_id, germplasm_id=context['germplasm_id'], time=None, reproduction=None, synonyms=[]
    ))
    await bus.handle(UpdatePerson(agent_id=user_id, person_id=context['person_id'], institution=None))
    await bus.handle(UpdateTeam(agent_id=user_id, team_id=context['team_id'], fullname=""))
    await bus.handle(UpdateExternalReference(agent_id=user_id, reference_id=context['reference_id'], external_id=None))
    await bus.handle(UpdateSubject(
        agent_id=user_id, ontology_entry_id=context['subject_id'], abbreviation=None, synonyms=None, description=""
    ))
    # changes to an active entry are patches the next commit applies
    async with uow_factory.get_uow(user_id=user_id) as uow:
        await uow.ontology.commit_version(version_change=VersionChange.PATCH)
        await uow.commit()

    async with uow_factory.get_uow(user_id=user_id) as uow:
        germplasm = await uow.germplasm.get_entry(context['germplasm_id'])
        assert (germplasm.description, germplasm.synonyms, germplasm.time, germplasm.reproduction) == ("Clone", [], None, None)
        person = await uow.repositories.people.get(person_id=context['person_id'])
        assert person.institution is None
        team = (await uow.repositories.team_trees.get(team_id=context['team_id'])).get_team(context['team_id'])
        assert team.fullname is None
        reference = await uow.repositories.references.get(reference_id=context['reference_id'])
        assert (reference.description, reference.url, reference.external_id) == ("A data portal", "https://example.org/data", None)
        subject = await uow.ontology.get_entry(context['subject_id'])
        assert (subject.name, subject.abbreviation, subject.synonyms, subject.description) == ("Clearing Shoot", None, [], None)
