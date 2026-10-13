import csv

import pytest
import pytest_asyncio
from numpy import datetime64, datetime_data

from breedgraph.domain.model.accounts import OntologyRole
from breedgraph.domain.model.ontology import (
    OntologyEntryLabel, ScaleType, ObservationMethodType, ControlMethodType, SubjectInput, TraitInput,
    ObservationMethodInput, ScaleInput, ScaleCategoryInput, VariableInput, ConditionInput, ControlMethodInput,
    FactorInput, RecordGroupTypeInput
)
from breedgraph.domain.model.programs import ProgramInput, TrialInput, StudyInput, RecordGroupingInput, GroupingScope

from breedcafs_migration import datasets, programs
from breedcafs_migration.bootstrap import MigrationContext
from breedcafs_migration.datasets import prepare_breedcafs_datasets, DESIGN
from breedcafs_migration.ontology import OntologyIds
from breedcafs_migration.programs import ProgramIds

from tests.breedgraph.scenarios.account_builder import AccountBuilder
from tests.breedgraph.scenarios.block_builder import BlockBuilder

# As BreedCAFS stored dates: at 12:00 where no time of day was entered
T1, T2, T3 = '1558353600000', '1558440000000', '1558526400000'  # 2019-05-20, 21 and 22 at 12:00
T4 = '1558319460000'  # 2019-05-20 at 02:31, entered as text_time "2:31"


def record(submission, item, input_name, value, time='', replicate='', record_type='Trait', start='', end='', text_time=''):
    submission_time, submitter_id = submission
    return {
        'record_id': '', 'submission_time': submission_time, 'submitter_id': submitter_id, 'item_uid': item,
        'record_type': record_type, 'input': input_name, 'value': value, 'time': time, 'text_time': text_time,
        'start': start, 'text_start_time': '', 'end': end, 'text_end_time': '', 'replicate': replicate
    }


A, B, NONE = ('100', '7'), ('200', '8'), ('', '')
RECORDS = [
    record(A, '1_T1', 'Tree height', '12.5', T1, '0'),
    record(A, '1_T2', 'Tree height', '13', T1, '0'),
    record(A, '1_T1', 'Flowering', 'True', T1),
    record(A, '1_T1', 'Fₒ', '5', T2, '1'),                    # no apparatus recorded: the only apparatus of its input
    record(A, '1_T1', 'Fᵥ / Fₘ', '0.8', T2, '1'),             # no apparatus recorded, but with a JIP-test parameter
    record(A, '1_T2', 'Photosynthetic Analysis Apparatus', 'MiniPAM', T3, record_type='Trait'),
    record(A, '1_T2', 'Fᵥ / Fₘ', '0.7', T3),
    record(A, '1_S1', '5CQA', '3.2', T4, text_time='2:31'),   # a metabolite, wherever recorded
    record(A, '1_T1', 'Set harvest time', '12:00', record_type='Property'),
    record(B, '22_T1', 'Shade level', '40', record_type='Condition', start='1438430400000', end='False'),
    record(B, '22_T1', 'Tree height', '2', T1, '0'),
    # Loaded without a submission: one repeating a record of submission A (same item, input, value and replicate),
    # left out whatever its date; one not, kept in a dataset of its own
    record(NONE, '1_T1', 'Tree height', '12.5', T3, '0'),
    record(NONE, '1_T1', 'Tree height', '11', T3, '0'),
]
FILES = {
    'records.csv': RECORDS,
    'factor_records.csv': [{'item_uid': '22_T1', 'factor': 'Stratum', 'category': 'Upper'}],
    'input_details_curated.csv': [
        {'name': '"5CQA"', 'terms': '[“Metabolites”]'}, {'name': '"Tree height"', 'terms': '[“Phenotype”]'},
    ],
    'field_farm_region_country.csv': [{'field_uid': '1', 'country': '"Vietnam"'}, {'field_uid': '22', 'country': '"Nicaragua"'}],
}


def write_csv(path, rows):
    with open(path, 'w', newline='', encoding='utf-8-sig') as f:
        writer = csv.DictWriter(f, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)


async def concept(ontology, subject_id, name, scale_type, categories=(), factor=False) -> int:
    category_ids = [(await ontology.create_entry(ScaleCategoryInput(name=c))).id for c in categories]
    scale = await ontology.create_scale(ScaleInput(name=f"{name} scale", scale_type=scale_type), categories=category_ids)
    if factor:
        condition = await ontology.create_condition(ConditionInput(name=f"{name} condition"), subjects=[subject_id])
        method = await ontology.create_entry(ControlMethodInput(name=f"{name} method", control_type=ControlMethodType.MANAGEMENT))
        return (await ontology.create_factor(FactorInput(name=name), condition.id, method.id, scale.id)).id
    trait = await ontology.create_trait(TraitInput(name=f"{name} trait"), subjects=[subject_id])
    method = await ontology.create_entry(ObservationMethodInput(name=f"{name} method", observation_type=ObservationMethodType.MEASUREMENT))
    return (await ontology.create_variable(VariableInput(name=name), trait.id, method.id, scale.id)).id


@pytest_asyncio.fixture(scope="module", loop_scope="session")
async def datasets_context(isolated_state, uow_factory) -> dict:
    account = await AccountBuilder(uow_factory=uow_factory).account_with_affiliations(ontology_role=OntologyRole.EDITOR)
    user_id, team_id = account['user_id'], account['team_id']
    async with uow_factory.get_uow(user_id=user_id) as uow:
        ontology = uow.ontology
        subject = await ontology.create_entry(SubjectInput(name="Tree"))
        variable, factor = OntologyEntryLabel.VARIABLE, OntologyEntryLabel.FACTOR
        inputs = {
            ("Tree height", ''): (variable, await concept(ontology, subject.id, "Height", ScaleType.NUMERICAL)),
            ("Flowering", ''): (variable, await concept(ontology, subject.id, "Flower presence", ScaleType.NOMINAL, ["Yes", "No"])),
            ("Shade level", ''): (factor, await concept(ontology, subject.id, "Shade", ScaleType.NUMERICAL, factor=True)),
            ("Fₒ", 'PocketPEA'): (variable, await concept(ontology, subject.id, "Fo (PocketPEA)", ScaleType.NUMERICAL)),
            ("Fᵥ / Fₘ", 'PocketPEA'): (variable, await concept(ontology, subject.id, "Fv/Fm (PocketPEA)", ScaleType.NUMERICAL)),
            ("Fᵥ / Fₘ", 'MiniPAM'): (variable, await concept(ontology, subject.id, "Fv/Fm (MiniPAM)", ScaleType.NUMERICAL)),
            ("5CQA", ''): (variable, await concept(ontology, subject.id, "5CQA", ScaleType.NUMERICAL)),
        }
        stratum = await concept(ontology, subject.id, "Stratum", ScaleType.ORDINAL, ["Lower", "Middle", "Upper"], factor=True)
        replicate_type = await ontology.create_entry(RecordGroupTypeInput(name="Replicate"))
        await uow.commit()

    async with uow_factory.get_uow(user_id=user_id, write_team=team_id) as uow:
        program = await uow.repositories.programs.create(ProgramInput(name="BreedCAFS"))
        program.add_trial(TrialInput(name="Trials"))
        await uow.repositories.programs.update_seen()
        trial = next(iter(program.trials.values()))
        for name in ("Vietnam", "Nicaragua", "Metabolomics"):
            trial.add_study(StudyInput(name=name, groupings=[
                RecordGroupingInput(type=replicate_type.id, name="Replicate", scope=GroupingScope.DATASET_SCOPED)
            ]))
        await uow.repositories.programs.update_seen()
        program_ids = ProgramIds(program_id=program.id)
        for study in next(iter(program.trials.values())).studies.values():
            program_ids.studies[study.name] = study.id
            program_ids.replicate_groupings[study.name] = study.get_grouping(name="Replicate").id
        await uow.commit()

    block_builder = BlockBuilder(uow_factory=uow_factory)
    units = {uid: await block_builder.unit(user_id=user_id, team_id=team_id) for uid in ('1_T1', '1_T2', '1_S1', '22_T1')}
    return {
        'context': MigrationContext(user_id=user_id, team_id=team_id),
        'ontology': OntologyIds(inputs=inputs, design_factors={"Stratum": stratum}),
        'programs': program_ids,
        'units': units,
    }


@pytest.fixture
def data_dir(tmp_path, monkeypatch):
    for name, rows in FILES.items():
        write_csv(tmp_path / name, rows)
    for module in (datasets, programs):
        monkeypatch.setattr(module, 'BREEDCAFS_DATA_DIR', tmp_path)
    return tmp_path


async def prepare(uow_factory, context):
    return await prepare_breedcafs_datasets(
        uow_factory, context['context'], context['ontology'], context['programs'], context['units']
    )


@pytest.mark.asyncio(loop_scope="session")
async def test_prepare_datasets(uow_factory, datasets_context, data_dir):
    inputs = datasets_context['ontology'].inputs
    studies = datasets_context['programs'].studies
    units = datasets_context['units']
    concept_of = lambda input_name, apparatus='': inputs[(input_name, apparatus)][1]

    ids = await prepare(uow_factory, datasets_context)

    assert set(ids.datasets) == {
        ('Vietnam', concept_of('Tree height'), *A),
        ('Vietnam', concept_of('Tree height'), *NONE),
        ('Vietnam', concept_of('Flowering'), *A),
        ('Vietnam', concept_of('Fₒ', 'PocketPEA'), *A),
        ('Vietnam', concept_of('Fᵥ / Fₘ', 'PocketPEA'), *A),
        ('Vietnam', concept_of('Fᵥ / Fₘ', 'MiniPAM'), *A),
        ('Metabolomics', concept_of('5CQA'), *A),
        ('Nicaragua', concept_of('Shade level'), *B),
        ('Nicaragua', concept_of('Tree height'), *B),
        ('Nicaragua', datasets_context['ontology'].design_factors['Stratum'], DESIGN, ''),
    }
    assert ids.records == 11
    assert ids.repeats_left_out == 1

    async with uow_factory.get_uow(user_id=datasets_context['context'].user_id) as uow:
        async def dataset(study, concept, submission=A):
            return await uow.repositories.datasets.get(dataset_id=ids.datasets[(study, concept, *submission)])

        heights = await dataset('Vietnam', concept_of('Tree height'))
        assert heights.study == studies['Vietnam']
        assert sorted((r.unit, r.value) for r in heights.records) == sorted([(units['1_T1'], '12.5'), (units['1_T2'], '13')])
        [loaded] = (await dataset('Vietnam', concept_of('Tree height'), NONE)).records
        assert (loaded.unit, loaded.value) == (units['1_T1'], '11')
        replicate = datasets_context['programs'].replicate_groupings['Vietnam']
        for r in heights.records:
            # The date alone, as no time of day was entered
            assert (r.start, r.end) == (datetime64('2019-05-20'), datetime64('2019-05-20'))
            assert datetime_data(r.start.dtype)[0] == 'D'
            assert [(g.id, g.code) for g in r.groups] == [(replicate, '0')]

        [flowering] = (await dataset('Vietnam', concept_of('Flowering'))).records
        assert flowering.value == "Yes"
        [mini_pam] = (await dataset('Vietnam', concept_of('Fᵥ / Fₘ', 'MiniPAM'))).records
        assert (mini_pam.unit, mini_pam.value) == (units['1_T2'], '0.7')
        [pocket_pea] = (await dataset('Vietnam', concept_of('Fᵥ / Fₘ', 'PocketPEA'))).records
        assert (pocket_pea.unit, pocket_pea.value) == (units['1_T1'], '0.8')
        [shade] = (await dataset('Nicaragua', concept_of('Shade level'), B)).records
        assert (shade.start, shade.end) == (datetime64('2015-08-01'), None)
        [metabolite] = (await dataset('Metabolomics', concept_of('5CQA'))).records
        # To the minute, as the time of day was entered
        assert metabolite.start == datetime64('2019-05-20T02:31')
        assert datetime_data(metabolite.start.dtype)[0] == 'm'
        [stratum] = (await dataset('Nicaragua', datasets_context['ontology'].design_factors['Stratum'], (DESIGN, ''))).records
        assert (stratum.unit, stratum.value) == (units['22_T1'], 'Upper')

        # Replicate codes are compared only within the datasets of a submission in a study
        program = await uow.repositories.programs.get(study_id=studies['Vietnam'])
        scopes = lambda study: [
            set(scope.dataset_ids) for scope in program.get_study(studies[study]).get_grouping(name="Replicate").dataset_scopes
        ]
        assert {dataset_id for key, dataset_id in ids.datasets.items() if key[0] == 'Vietnam' and key[2] == A[0]} in scopes('Vietnam')
        assert scopes('Nicaragua') == [{ids.datasets[('Nicaragua', concept_of(name), *B)] for name in ('Shade level', 'Tree height')}]

    with open(data_dir / 'dataset_ids.csv') as f:
        assert len(list(csv.DictReader(f))) == len(ids.datasets)

    again = await prepare(uow_factory, datasets_context)
    assert again.created == 0
    assert again.datasets == ids.datasets
