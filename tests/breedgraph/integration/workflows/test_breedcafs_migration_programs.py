import csv

import pytest
import pytest_asyncio
from numpy import datetime64

from breedgraph.domain.model.accounts import OntologyRole
from breedgraph.domain.model.controls import ReadRelease
from breedgraph.domain.model.ontology import RecordGroupTypeInput, RecordGroupExtent
from breedgraph.domain.model.programs import GroupingScope

from breedcafs_migration import programs
from breedcafs_migration.bootstrap import MigrationContext
from breedcafs_migration.programs import prepare_breedcafs_programs, study_for, STUDIES, TRIALS

from tests.breedgraph.scenarios.account_builder import AccountBuilder

# As exported: names wrapped in extra quotes, terms with typographic quotes,
# times in milliseconds since the epoch, and False where not given
FILES = {
    'input_details_curated.csv': [
        {'name': '"Tree height"', 'terms': '[“Phenotype”]'},
        {'name': '"5CQA"', 'terms': '[“Metabolites”]'},
        {'name': '"Shade level"', 'terms': '[“Environment”]'},
    ],
    'field_farm_region_country.csv': [
        {'field_uid': '1', 'country': '"Vietnam"'},
        {'field_uid': '22', 'country': '"Nicaragua"'},
    ],
    'records.csv': [
        {'input': 'Tree height', 'item_uid': '1_T1', 'time': '1558310400000', 'start': '', 'end': ''},  # 2019-05-20
        {'input': 'Tree height', 'item_uid': '1_T2', 'time': '1621036800000', 'start': '', 'end': ''},  # 2021-05-15
        {'input': '5CQA', 'item_uid': '1_S1', 'time': '1519171200000', 'start': '', 'end': ''},  # 2018-02-21
        {'input': 'Shade level', 'item_uid': '22_T1', 'time': '', 'start': '1438387200000', 'end': 'False'},  # 2015-08-01
        {'input': 'Shade level', 'item_uid': '22_T2', 'time': '', 'start': 'False', 'end': 'False'},
        {'input': 'Set planting date', 'item_uid': '22_T1', 'time': '', 'start': '', 'end': ''},
    ],
    'curves.csv': [{'input': 'Fluorescence ~ Time', 'item_uid': '22_S1', 'time': '1574899200000'}],  # 2019-11-28
}


def write_csv(path, rows):
    with open(path, 'w', newline='', encoding='utf-8-sig') as f:
        writer = csv.DictWriter(f, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)


@pytest_asyncio.fixture(scope="module", loop_scope="session")
async def programs_context(isolated_state, uow_factory) -> dict:
    migration = await AccountBuilder(uow_factory=uow_factory).account_with_affiliations(ontology_role=OntologyRole.EDITOR)
    async with uow_factory.get_uow(user_id=migration['user_id']) as uow:
        replicate = await uow.ontology.create_entry(RecordGroupTypeInput(name="Replicate", extent=RecordGroupExtent.WITHIN_UNIT))
        await uow.commit()
    return {
        'context': MigrationContext(user_id=migration['user_id'], team_id=migration['team_id']),
        'record_group_types': {"Replicate": replicate.id},
    }


def test_study_for():
    assert study_for({"Phenotype"}, "Nicaragua") == "Nicaragua"
    assert study_for({"Metabolites"}, "Vietnam") == "Metabolomics"
    assert study_for({"Elements"}, "Costa Rica") == "Mineral analysis"
    assert study_for(set(), "Denmark") == "Denmark"
    with pytest.raises(ValueError, match="France"):
        study_for(set(), "France")


@pytest.mark.asyncio(loop_scope="session")
async def test_prepare_programs(uow_factory, programs_context, tmp_path, monkeypatch):
    for name, rows in FILES.items():
        write_csv(tmp_path / name, rows)
    monkeypatch.setattr(programs, 'BREEDCAFS_DATA_DIR', tmp_path)
    context = programs_context['context']

    ids = await prepare_breedcafs_programs(uow_factory, context, programs_context['record_group_types'])

    assert set(ids.trials) == set(TRIALS)
    assert set(ids.studies) == set(STUDIES)
    assert ids.created == 1 + len(TRIALS) + len(STUDIES)

    async with uow_factory.get_uow(user_id=context.user_id) as uow:
        program = await uow.repositories.programs.get(program_id=ids.program_id)
        assert (program.name, program.fullname) == ("BreedCAFS", "Breeding Coffee for Agroforestry Systems")
        for key, (trial_name, name, _) in STUDIES.items():
            trial = program.trials[ids.trials[trial_name]]
            study = trial.studies[ids.studies[key]]
            assert study.name == name
            [grouping] = study.groupings
            assert (grouping.id, grouping.name, grouping.scope, grouping.type) == (
                ids.replicate_groupings[key], "Replicate", GroupingScope.DATASET_SCOPED,
                programs_context['record_group_types']["Replicate"]
            )
        def study(key):
            return program.trials[ids.trials[STUDIES[key][0]]].studies[ids.studies[key]]

        assert (study("Vietnam").start, study("Vietnam").end) == (datetime64('2019-05-20'), datetime64('2021-05-15'))
        assert (study("Nicaragua").start, study("Nicaragua").end) == (datetime64('2015-08-01'), datetime64('2019-11-28'))
        assert (study("Metabolomics").start, study("Metabolomics").end) == (datetime64('2018-02-21'), datetime64('2018-02-21'))
        assert (study("Cameroon").start, study("Cameroon").end) == (None, None)

        controller = await uow.controls.get_controller(program.label, program.id)
        assert controller.release is ReadRelease.PRIVATE
        assert set(controller.controls) == {context.team_id}

    with open(tmp_path / 'study_ids.csv') as f:
        assert {row['study']: int(row['study_id']) for row in csv.DictReader(f)} == ids.studies

    again = await prepare_breedcafs_programs(uow_factory, context, programs_context['record_group_types'])
    assert again.created == 0
    assert (again.program_id, again.trials, again.studies, again.replicate_groupings) == (
        ids.program_id, ids.trials, ids.studies, ids.replicate_groupings
    )
