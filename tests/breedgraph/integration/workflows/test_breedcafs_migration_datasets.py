import csv
import json

import pytest
import pytest_asyncio
from numpy import datetime64, datetime_data

from breedgraph.domain.model.accounts import OntologyRole
from breedgraph.domain.model.ontology import (
    VersionChange,
    OntologyEntryLabel, ScaleType, ObservationMethodType, ControlMethodType, SubjectInput, TraitInput,
    ObservationMethodInput, ScaleInput, ScaleCategoryInput, VariableInput, ConditionInput, ControlMethodInput,
    FactorInput, RecordGroupTypeInput, RecordGroupExtent
)
from breedgraph.domain.model.programs import ProgramInput, TrialInput, StudyInput, RecordGroupingInput, GroupingScope

from breedcafs_migration import datasets, programs, units as migration_units
from breedcafs_migration.bootstrap import MigrationContext
from breedcafs_migration.datasets import prepare_breedcafs_datasets, DESIGN
from breedcafs_migration.ontology import OntologyIds
from breedcafs_migration.programs import ProgramIds

from tests.breedgraph.scenarios.account_builder import AccountBuilder
from tests.breedgraph.scenarios.unit_graph_builder import UnitGraphBuilder

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
    # Branches are not units: on the tree they were taken from, with branch and stratum codes
    record(B, '22_S1', 'Fruit count', '4', T1, '0'),
    record(B, '22_S2', 'Fruit count', '6', T1, '0'),
    record(B, '22_S1', 'Node count', '9', T1, '0'),
    # Leaves measured once are not units either: on their tree, with a leaf code
    record(B, '22_S4', 'Leaf length', '7', T1, '0'),
    # The harvest of a Leaves sample left out, as nothing more was recorded for it
    record(B, '22_S5', 'Set harvest date', '2019-05-20', T1),
    # Loaded without a submission: one repeating a record of submission A (same item, input, value and replicate),
    # left out whatever its date; one not, kept in a dataset of its own
    record(NONE, '1_T1', 'Tree height', '12.5', T3, '0'),
    record(NONE, '1_T1', 'Tree height', '11', T3, '0'),
]
FILES = {
    'records.csv': RECORDS,
    'factor_records.csv': [{'item_uid': '22_T1', 'factor': 'Shade Treatment', 'category': 'Shade'}],
    'item_name_subject_sources_sinks.csv': [
        {
            'item_uid': f'"""{uid}"""', 'name': '"""Block 1"""' if subject == 'Block' else 'null', 'subject': f'"""{subject}"""',
            'source_items': json.dumps(sources), 'sink_items': '[]'
        }
        for uid, subject, sources in (
            ('22', 'Field', []), ('22_B1', 'Block', [22]), ('22_T1', 'Tree', ['22_B1', 22]),
            ('22_S1', 'Branch', ['22_T1']), ('22_S2', 'Branch', ['22_T1']), ('22_S4', 'Leaf', ['22_T1']), ('22_S5', 'Leaves', ['22_T1']),
        )
    ],
    # read for the unit plan, but not needed here
    'item_variety.csv': [{'item_uid': '"""22_T9"""', 'variety': '"""Catimor"""'}],
    'unit_positions.csv': [{
        'field_uid': '22', 'item_uid': '"""22_T9"""', 'layout_type': '"""row_and_tree"""', 'layout_level': '"""field"""',
        'layout_name': '""""""', 'row': '1.0', 'column': '1.0', 'stratum': 'null'
    }],
    'sample_positions.csv': [{'item_uid': '"""22_S9"""', 'location': '"""Montpellier/ IRD"""', 'date': '"""2019-03-25"""'}],
    'skipped_items.csv': [{'item_uid': '1_S9', 'reason': ''}],
    'branch_strata.csv': [{'item_uid': '22_S1', 'strata': '["Upper"]'}, {'item_uid': '22_S2', 'strata': '["Lower"]'}],
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
            ("Fruit count", ''): (variable, await concept(ontology, subject.id, "Fruit count", ScaleType.NUMERICAL)),
            ("Node count", ''): (variable, await concept(ontology, subject.id, "Node count", ScaleType.NUMERICAL)),
            ("Leaf length", ''): (variable, await concept(ontology, subject.id, "Leaf length", ScaleType.NUMERICAL)),
        }
        shade_treatment = await concept(ontology, subject.id, "Shade Treatment", ScaleType.NOMINAL, ["Full Sun", "Shade"], factor=True)
        replicate_type = await ontology.create_entry(RecordGroupTypeInput(name="Replicate", default_extent=RecordGroupExtent.WITHIN_UNIT))
        branch_type = await ontology.create_entry(RecordGroupTypeInput(name="Branch", default_extent=RecordGroupExtent.WITHIN_UNIT))
        stratum_type = await ontology.create_entry(RecordGroupTypeInput(name="Stratum", default_extent=RecordGroupExtent.SHARED))
        leaf_type = await ontology.create_entry(RecordGroupTypeInput(name="Leaf", default_extent=RecordGroupExtent.WITHIN_UNIT))
        block_type = await ontology.create_entry(RecordGroupTypeInput(name="Block", default_extent=RecordGroupExtent.WITHIN_GRAPH))
        # as the migration does: data cites entries of a committed version
        await ontology.commit_version(version_change=VersionChange.MINOR)
        await uow.commit()

    async with uow_factory.get_uow(user_id=user_id, write_team=team_id) as uow:
        program = await uow.repositories.programs.create(ProgramInput(name="BreedCAFS"))
        program.add_trial(TrialInput(name="Trials"))
        await uow.repositories.programs.update_seen()
        trial = next(iter(program.trials.values()))
        for name in ("Vietnam", "Nicaragua", "Metabolomics"):
            groupings = [RecordGroupingInput(
                type=replicate_type.id, name="Replicate", scope=GroupingScope.DATASET_SCOPED,
                extent=RecordGroupExtent.WITHIN_UNIT
            )]
            if name == "Nicaragua":
                groupings += [
                    RecordGroupingInput(
                        type=group_type.id, name=group_type.name, scope=GroupingScope.STUDY_WIDE,
                        extent=group_type.default_extent
                    )
                    for group_type in (block_type, branch_type, stratum_type, leaf_type)
                ]
            trial.add_study(StudyInput(name=name, groupings=groupings))
        await uow.repositories.programs.update_seen()
        program_ids = ProgramIds(program_id=program.id)
        for study in next(iter(program.trials.values())).studies.values():
            program_ids.studies[study.name] = study.id
            program_ids.replicate_groupings[study.name] = study.get_grouping(name="Replicate").id
        nicaragua = next(study for study in next(iter(program.trials.values())).studies.values() if study.name == "Nicaragua")
        program_ids.code_groupings["Nicaragua"] = {
            name: nicaragua.get_grouping(name=name).id for name in ("Block", "Branch", "Stratum", "Leaf")
        }
        await uow.commit()

    unit_graph_builder = UnitGraphBuilder(uow_factory=uow_factory)
    units = {uid: await unit_graph_builder.unit(user_id=user_id, team_id=team_id) for uid in ('1_T1', '1_T2', '1_S1', '22_T1')}
    return {
        'context': MigrationContext(user_id=user_id, team_id=team_id),
        'ontology': OntologyIds(inputs=inputs, design_factors={"Shade Treatment": shade_treatment}),
        'programs': program_ids,
        'units': units,
    }


@pytest.fixture
def data_dir(tmp_path, monkeypatch):
    for name, rows in FILES.items():
        write_csv(tmp_path / name, rows)
    for module in (datasets, programs, migration_units):
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
        ('Nicaragua', concept_of('Fruit count'), *B),
        ('Nicaragua', concept_of('Node count'), *B),
        ('Nicaragua', concept_of('Leaf length'), *B),
        ('Nicaragua', datasets_context['ontology'].design_factors['Shade Treatment'], DESIGN, ''),
    }
    assert ids.records == 15
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
            # code 0 marks a reading not replicated, so it is not migrated
            assert not r.groups

        [flowering] = (await dataset('Vietnam', concept_of('Flowering'))).records
        assert flowering.value == "Yes"
        [mini_pam] = (await dataset('Vietnam', concept_of('Fᵥ / Fₘ', 'MiniPAM'))).records
        assert (mini_pam.unit, mini_pam.value) == (units['1_T2'], '0.7')
        [pocket_pea] = (await dataset('Vietnam', concept_of('Fᵥ / Fₘ', 'PocketPEA'))).records
        assert (pocket_pea.unit, pocket_pea.value) == (units['1_T1'], '0.8')
        # a real replicate code is kept
        assert [(g.id, g.code) for g in pocket_pea.groups] == [(replicate, '1')]
        [shade] = (await dataset('Nicaragua', concept_of('Shade level'), B)).records
        assert (shade.start, shade.end) == (datetime64('2015-08-01'), None)
        [metabolite] = (await dataset('Metabolomics', concept_of('5CQA'))).records
        # To the minute, as the time of day was entered
        assert metabolite.start == datetime64('2019-05-20T02:31')
        assert datetime_data(metabolite.start.dtype)[0] == 'm'
        [treatment] = (await dataset('Nicaragua', datasets_context['ontology'].design_factors['Shade Treatment'], (DESIGN, ''))).records
        assert (treatment.unit, treatment.value) == (units['22_T1'], 'Shade')

        codes = datasets_context['programs'].code_groupings['Nicaragua']
        block, branch, stratum, leaf = (codes[name] for name in ("Block", "Branch", "Stratum", "Leaf"))
        groups = lambda r: {(g.id, g.code) for g in r.groups}
        # what is in a BreedCAFS block, or was taken from one, has its code
        [tree_height] = (await dataset('Nicaragua', concept_of('Tree height'), B)).records
        assert groups(tree_height) == {(block, 'Block 1')}
        fruit = (await dataset('Nicaragua', concept_of('Fruit count'), B)).records
        assert sorted((r.unit, r.value, frozenset(groups(r))) for r in fruit) == [
            (units['22_T1'], '4', frozenset({(branch, '22_S1'), (stratum, 'Upper'), (block, 'Block 1')})),
            (units['22_T1'], '6', frozenset({(branch, '22_S2'), (stratum, 'Lower'), (block, 'Block 1')})),
        ]
        [nodes] = (await dataset('Nicaragua', concept_of('Node count'), B)).records
        assert (nodes.unit, groups(nodes)) == (units['22_T1'], {(branch, '22_S1'), (stratum, 'Upper'), (block, 'Block 1')})
        [leaf_length] = (await dataset('Nicaragua', concept_of('Leaf length'), B)).records
        assert (leaf_length.unit, groups(leaf_length)) == (units['22_T1'], {(leaf, '22_S4'), (block, 'Block 1')})

        # Replicate codes are compared only within the datasets of a submission in a study
        program = await uow.repositories.programs.get(study_id=studies['Vietnam'])
        scopes = lambda study: [
            set(scope.dataset_ids) for scope in program.get_study(studies[study]).get_grouping(name="Replicate").dataset_scopes
        ]
        assert {dataset_id for key, dataset_id in ids.datasets.items() if key[0] == 'Vietnam' and key[2] == A[0]} in scopes('Vietnam')
        assert scopes('Nicaragua') == [{
            ids.datasets[('Nicaragua', concept_of(name), *B)]
            for name in ('Shade level', 'Tree height', 'Fruit count', 'Node count', 'Leaf length')
        }]

    with open(data_dir / 'dataset_ids.csv') as f:
        assert len(list(csv.DictReader(f))) == len(ids.datasets)

    again = await prepare(uow_factory, datasets_context)
    assert again.created == 0
    assert again.datasets == ids.datasets
