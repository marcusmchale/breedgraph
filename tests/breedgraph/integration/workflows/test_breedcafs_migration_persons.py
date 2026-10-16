import csv

import pytest
import pytest_asyncio

from breedgraph.domain.model.accounts import OntologyRole
from breedgraph.domain.model.controls import Access, ReadRelease
from breedgraph.domain.model.datasets import DatasetInput
from breedgraph.domain.model.ontology import (
    OntologyEntryLabel, ScaleType, ObservationMethodType, SubjectInput, TraitInput, ObservationMethodInput, ScaleInput,
    VariableInput
)
from breedgraph.domain.model.people import LawfulBasis
from breedgraph.domain.model.programs import ProgramInput, TrialInput, StudyInput

from breedcafs_migration import persons
from breedcafs_migration.bootstrap import MigrationContext, MigrationSettingsError
from breedcafs_migration.curves import CurveIds
from breedcafs_migration.datasets import DatasetIds, DESIGN
from breedcafs_migration.ontology import OntologyIds
from breedcafs_migration.persons import prepare_breedcafs_persons

from tests.breedgraph.scenarios.account_builder import AccountBuilder
from tests.breedgraph.scenarios.team_tree_builder import TeamTreeBuilder

TERMS_VERSION = "test"
CIRAD = "Centre de Coopération Internationale en Recherche Agronomique pour le Développement"
FILES = {
    'persons.csv': [
        {'Name': 'Ana Pérez', 'institution': CIRAD, 'record_count': '10'},
        {'Name': 'J. Smith', 'institution': 'University of Copenhagen', 'record_count': '5'},
    ],
    'attribution_persons.csv': [
        {'attribution': 'Ana', 'partner': 'CIRAD', 'Name': 'Ana Pérez', 'record_count': '1', 'submission_count': '1', 'input_count': '1'},
        {'attribution': 'Ana & John', 'partner': 'CIRAD', 'Name': 'Ana Pérez; J. Smith', 'record_count': '1', 'submission_count': '1', 'input_count': '1'},
        {'attribution': 'unknown', 'partner': 'CIRAD', 'Name': '', 'record_count': '1', 'submission_count': '1', 'input_count': '1'},
    ],
    'submissions.csv': [
        {'submission_time': '100', 'submitter_id': '7', 'partner': 'CIRAD', 'attribution': 'Ana', 'input': 'Tree height'},
        {'submission_time': '100', 'submitter_id': '7', 'partner': 'CIRAD', 'attribution': 'Ana & John', 'input': 'Tree height'},
        {'submission_time': '100', 'submitter_id': '7', 'partner': 'CIRAD', 'attribution': 'Ana', 'input': 'Other input'},
        {'submission_time': '200', 'submitter_id': '8', 'partner': 'CIRAD', 'attribution': 'unknown', 'input': 'Tree height'},
    ],
    # submitter 7 is J. Smith, who also recorded data; submitter 8 is not credited
    'submitter_persons.csv': [
        {'submitter_id': '7', 'submitter': 'jsmith', 'partner': 'CIRAD', 'Name': 'J. Smith'},
        {'submitter_id': '8', 'submitter': 'other', 'partner': 'CIRAD', 'Name': ''},
    ],
}


def write_csv(path, rows):
    with open(path, 'w', newline='', encoding='utf-8-sig') as f:
        writer = csv.DictWriter(f, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)


async def declared_team_tree(uow_factory) -> dict:
    """An account with write access to a team under the root of a team tree with a declared legal entity"""
    account = await AccountBuilder(uow_factory=uow_factory).account_with_affiliations(ontology_role=OntologyRole.EDITOR)
    await TeamTreeBuilder(uow_factory=uow_factory).authorise_access(
        user_id=account['user_id'], team_id=account['team_id'], access=Access.ADMIN, heritable=True
    )
    async with uow_factory.get_uow(user_id=account['user_id']) as uow:
        team_tree = await uow.repositories.team_trees.get(team_id=account['team_id'])
        team_tree.declare_legal_entity(
            agent_id=account['user_id'], team_id=account['team_id'], legal_name="University",
            privacy_contact="dataprotection@example.org", terms_version=TERMS_VERSION, current_terms_version=TERMS_VERSION
        )
        await uow.commit()
    return account


@pytest_asyncio.fixture(scope="module", loop_scope="session")
async def persons_context(isolated_state, uow_factory) -> dict:
    account = await declared_team_tree(uow_factory)
    user_id, team_id = account['user_id'], account['team_id']
    async with uow_factory.get_uow(user_id=user_id) as uow:
        ontology = uow.ontology
        subject = await ontology.create_entry(SubjectInput(name="Tree"))
        trait = await ontology.create_trait(TraitInput(name="Height"), subjects=[subject.id])
        method = await ontology.create_entry(ObservationMethodInput(name="Measured", observation_type=ObservationMethodType.MEASUREMENT))
        scale = await ontology.create_scale(ScaleInput(name="cm", scale_type=ScaleType.NUMERICAL))
        variable = await ontology.create_variable(VariableInput(name="Tree height (cm)"), trait.id, method.id, scale.id)
        await uow.commit()

    async with uow_factory.get_uow(user_id=user_id, write_team=team_id) as uow:
        program = await uow.repositories.programs.create(ProgramInput(name="BreedCAFS"))
        program.add_trial(TrialInput(name="Field trials"))
        await uow.repositories.programs.update_seen()
        next(iter(program.trials.values())).add_study(StudyInput(name="Vietnam"))
        await uow.repositories.programs.update_seen()
        study_id = next(iter(next(iter(program.trials.values())).studies))
        dataset_ids = {}
        for key in (("Vietnam", variable.id, '100', '7'), ("Vietnam", variable.id, '200', '8'), ("Vietnam", variable.id, DESIGN, '')):
            dataset_ids[key] = (await uow.repositories.datasets.create(DatasetInput(concept=variable.id, study=study_id))).id
        await uow.commit()

    return {
        'context': MigrationContext(user_id=user_id, team_id=team_id),
        'ontology': OntologyIds(inputs={("Tree height", ''): (OntologyEntryLabel.VARIABLE, variable.id)}),
        'datasets': DatasetIds(datasets=dataset_ids),
        'variable': variable.id,
    }


@pytest.fixture
def data_dir(tmp_path, monkeypatch):
    for name, rows in FILES.items():
        write_csv(tmp_path / name, rows)
    monkeypatch.setattr(persons, 'BREEDCAFS_DATA_DIR', tmp_path)
    return tmp_path


async def prepare(uow_factory, context):
    return await prepare_breedcafs_persons(uow_factory, context['context'], context['ontology'], context['datasets'], CurveIds())


@pytest.mark.asyncio(loop_scope="session")
async def test_persons_require_a_legal_entity(uow_factory, persons_context, data_dir):
    account = await AccountBuilder(uow_factory=uow_factory).account_with_affiliations()
    context = {**persons_context, 'context': MigrationContext(user_id=account['user_id'], team_id=account['team_id'])}
    with pytest.raises(MigrationSettingsError, match="legal entity"):
        await prepare(uow_factory, context)


@pytest.mark.asyncio(loop_scope="session")
async def test_prepare_persons(uow_factory, persons_context, data_dir):
    context = persons_context['context']
    datasets = persons_context['datasets'].datasets
    variable = persons_context['variable']

    ids = await prepare(uow_factory, persons_context)

    assert set(ids.persons) == {('Ana Pérez', CIRAD), ('J. Smith', 'University of Copenhagen')}
    assert ids.created == 2
    ana, smith = ids.persons[('Ana Pérez', CIRAD)], ids.persons[('J. Smith', 'University of Copenhagen')]

    async with uow_factory.get_uow(user_id=context.user_id) as uow:
        person = await uow.repositories.people.get(person_id=ana)
        assert (person.name, person.institution, person.basis, person.informed_attestation) == (
            'Ana Pérez', CIRAD, LawfulBasis.PUBLIC_TASK, True
        )
        controller = await uow.controls.get_controller(person.label, person.id)
        assert controller.release is ReadRelease.PRIVATE
        assert set(controller.controls) == {context.team_id}

        submitted = await uow.repositories.datasets.get(dataset_id=datasets[("Vietnam", variable, '100', '7')])
        curation = (await uow.ontology.get_entry(name='Data curation', label=OntologyEntryLabel.ROLE)).id
        assert sorted((c.person, c.roles) for c in submitted.contributions) == sorted([(ana, []), (smith, [curation])])
        unattributed = await uow.repositories.datasets.get(dataset_id=datasets[("Vietnam", variable, '200', '8')])
        assert unattributed.contributions == []
        design = await uow.repositories.datasets.get(dataset_id=datasets[("Vietnam", variable, DESIGN, '')])
        assert design.contributions == []

    with open(data_dir / 'person_ids.csv') as f:
        assert {(row['Name'], row['institution']): int(row['person_id']) for row in csv.DictReader(f)} == ids.persons

    again = await prepare(uow_factory, persons_context)
    assert again.created == 0
    assert again.persons == ids.persons
    assert again.contributions == ids.contributions



@pytest.mark.asyncio(loop_scope="session")
async def test_submitter_persons_are_drafted_for_curation(data_dir):
    (data_dir / 'submitter_persons.csv').unlink()
    write_csv(data_dir / 'attribution_persons.csv', FILES['attribution_persons.csv'] + [
        {'attribution': 'submitter: jsmith', 'partner': 'CIRAD', 'Name': 'J. Smith', 'record_count': '1', 'submission_count': '1', 'input_count': '1'}
    ])
    write_csv(data_dir / 'submissions.csv', [{**row, 'submitter': {'7': 'jsmith', '8': 'other'}[row['submitter_id']]} for row in FILES['submissions.csv']])
    with pytest.raises(MigrationSettingsError, match="submitter_persons.csv is missing"):
        persons.read_submitter_persons()
    assert persons.draft_submitter_persons()
    assert persons.read_submitter_persons() == {'7': ['J. Smith'], '8': []}
    # a curated file is left as it is
    assert not persons.draft_submitter_persons()
