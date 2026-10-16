import csv
import json

import pytest
import pytest_asyncio
from numpy import datetime64

from breedgraph.adapters.neo4j.services.file_archival_service import Neo4jFileArchivalService
from breedgraph.service_layer.infrastructure import archival_service
from breedgraph.domain.model.accounts import OntologyRole
from breedgraph.domain.model.archive import ArchiveState
from breedgraph.domain.model.datasets import DatasetInput
from breedgraph.domain.model.ontology import (
    OntologyEntryLabel, ScaleType, ObservationMethodType, SubjectInput, TraitInput, ObservationMethodInput, ScaleInput,
    VariableInput, RecordGroupTypeInput, RecordGroupExtent
)
from breedgraph.domain.model.programs import ProgramInput, TrialInput, StudyInput, RecordGroupingInput, GroupingScope
from breedgraph.domain.model.references import DataFileStored, DataFormat

from breedcafs_migration import curves, programs
from breedcafs_migration.bootstrap import MigrationContext
from breedcafs_migration.curves import prepare_breedcafs_curves, file_name
from breedcafs_migration.datasets import DatasetIds
from breedcafs_migration.ontology import OntologyIds
from breedcafs_migration.programs import ProgramIds

from tests.breedgraph.scenarios.account_builder import AccountBuilder
from tests.breedgraph.scenarios.unit_graph_builder import UnitGraphBuilder

X = [1e-05, 2e-05, 0.5]
T1, T2 = '1558353600000', '1558396800000'  # 2019-05-20 at 12:00 (no time of day entered), 2019-05-21 at 00:00 (entered)
A, B = ('100', '7'), ('', '')


def curve(submission, item, time, y, text_time=''):
    return {
        'record_id': '', 'submission_time': submission[0], 'submitter_id': submission[1], 'item_uid': item,
        'input': 'Fluorescence ~ Time', 'time': time, 'text_time': text_time, 'replicate': '0',
        'x_values': json.dumps(X), 'y_values': json.dumps(y)
    }


FILES = {
    'curves.csv': [
        curve(A, '34_T1', T1, [1.0, 2.0, 3.0]),
        curve(A, '34_T2', T1, [4.0, 5.0, 6.0]),
        curve(B, '34_T1', T2, [7.0, 8.0, 9.0], text_time='00:00'),
        curve(B, '34_T1', T2, [1.0, 2.0, 3.0]),  # repeats 34_T1's curve of submission A, on another day: left out
    ],
    'input_details_curated.csv': [{'name': '"Fluorescence ~ Time"', 'terms': '[“Photosynthesis”]'}],
    'field_farm_region_country.csv': [{'field_uid': '34', 'country': '"Nicaragua"'}],
}


def write_csv(path, rows):
    with open(path, 'w', newline='', encoding='utf-8-sig') as f:
        writer = csv.DictWriter(f, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)


@pytest_asyncio.fixture(scope="module", loop_scope="session")
async def curves_context(isolated_state, uow_factory) -> dict:
    account = await AccountBuilder(uow_factory=uow_factory).account_with_affiliations(ontology_role=OntologyRole.EDITOR)
    user_id, team_id = account['user_id'], account['team_id']
    async with uow_factory.get_uow(user_id=user_id) as uow:
        ontology = uow.ontology
        subject = await ontology.create_entry(SubjectInput(name="Leaf"))
        trait = await ontology.create_trait(TraitInput(name="Fluorescence ~ Time"), subjects=[subject.id])
        method = await ontology.create_entry(ObservationMethodInput(name="PocketPEA", observation_type=ObservationMethodType.MEASUREMENT))
        scale = await ontology.create_scale(ScaleInput(name="Relative Intensity", scale_type=ScaleType.COMPLEX))
        variable = await ontology.create_variable(VariableInput(name="Fluorescence ~ Time (PocketPEA)"), trait.id, method.id, scale.id)
        other_scale = await ontology.create_scale(ScaleInput(name="Ratio", scale_type=ScaleType.NUMERICAL))
        other = await ontology.create_variable(VariableInput(name="Fv/Fm (PocketPEA)"), trait.id, method.id, other_scale.id)
        replicate_type = await ontology.create_entry(RecordGroupTypeInput(name="Replicate", default_extent=RecordGroupExtent.WITHIN_UNIT))
        await uow.commit()

    async with uow_factory.get_uow(user_id=user_id, write_team=team_id) as uow:
        program = await uow.repositories.programs.create(ProgramInput(name="BreedCAFS"))
        program.add_trial(TrialInput(name="Field trials"))
        await uow.repositories.programs.update_seen()
        next(iter(program.trials.values())).add_study(StudyInput(name="Nicaragua", groupings=[
            RecordGroupingInput(
                type=replicate_type.id, name="Replicate", scope=GroupingScope.DATASET_SCOPED,
                extent=RecordGroupExtent.WITHIN_UNIT
            )
        ]))
        await uow.repositories.programs.update_seen()
        study = next(iter(next(iter(program.trials.values())).studies.values()))
        program_ids = ProgramIds(program_id=program.id, studies={"Nicaragua": study.id})
        program_ids.replicate_groupings["Nicaragua"] = study.get_grouping(name="Replicate").id
        # A dataset already created for submission A, by the datasets phase
        other_dataset = await uow.repositories.datasets.create(DatasetInput(concept=other.id, study=study.id))
        await uow.commit()

    unit_graph_builder = UnitGraphBuilder(uow_factory=uow_factory)
    units = {uid: await unit_graph_builder.unit(user_id=user_id, team_id=team_id) for uid in ('34_T1', '34_T2')}
    return {
        'context': MigrationContext(user_id=user_id, team_id=team_id),
        'ontology': OntologyIds(inputs={("Fluorescence ~ Time", "PocketPEA"): (OntologyEntryLabel.VARIABLE, variable.id)}),
        'programs': program_ids,
        'units': units,
        'datasets': DatasetIds(datasets={("Nicaragua", other.id, *A): other_dataset.id}),
        'variable': variable.id,
    }


@pytest.fixture
def data_dir(tmp_path, monkeypatch):
    data = tmp_path / 'data'
    data.mkdir()
    for name, rows in FILES.items():
        write_csv(data / name, rows)
    for module in (curves, programs):
        monkeypatch.setattr(module, 'BREEDCAFS_DATA_DIR', data)
    monkeypatch.setattr(archival_service, 'FILE_STORAGE_PATH', str(tmp_path / 'files'))
    return tmp_path


async def prepare(uow_factory, context):
    return await prepare_breedcafs_curves(
        uow_factory, context['context'], context['ontology'], context['programs'], context['units'], context['datasets']
    )


@pytest.mark.asyncio(loop_scope="session")
async def test_prepare_curves(uow_factory, curves_context, data_dir):
    units = curves_context['units']
    study_id = curves_context['programs'].studies["Nicaragua"]
    replicate = curves_context['programs'].replicate_groupings["Nicaragua"]

    ids = await prepare(uow_factory, curves_context)

    key_a, key_b = ("Nicaragua", curves_context['variable'], *A), ("Nicaragua", curves_context['variable'], *B)
    assert set(ids.datasets) == {key_a, key_b}
    assert ids.created == 2
    assert file_name(key_a) == "fluorescence_curves_nicaragua_1970-01-01T00-00-00.csv"
    assert file_name(key_b) == "fluorescence_curves_nicaragua_without_submission.csv"

    # One data file per dataset
    with open(data_dir / 'data' / file_name(key_a)) as f:
        rows = list(csv.reader(f))
    assert rows[0] == ["item_uid", "unit_id", "time", "replicate", *[str(x) for x in X]]
    assert rows[1] == ['34_T1', str(units['34_T1']), '2019-05-20', '0', '1.0', '2.0', '3.0']
    assert len(rows) == 3
    with open(data_dir / 'data' / file_name(key_b)) as f:
        rows = list(csv.reader(f))
    assert [row[:3] for row in rows[1:]] == [['34_T1', str(units['34_T1']), '2019-05-21T00:00']]

    archival = Neo4jFileArchivalService(driver=uow_factory.driver, queue=None)
    async with uow_factory.get_uow(user_id=curves_context['context'].user_id) as uow:
        for key in (key_a, key_b):
            reference_id, dataset_id = ids.datasets[key]
            reference = await uow.repositories.references.get(reference_id=reference_id)
            assert isinstance(reference, DataFileStored)
            assert (reference.filename, reference.format, reference.content_type) == (file_name(key), DataFormat.CSV, "text/csv")
            assert reference.schema['index_columns'] == ["item_uid", "unit_id", "time", "replicate"]
            assert (data_dir / 'files' / reference.file_id).read_bytes() == (data_dir / 'data' / file_name(key)).read_bytes()
            assert (await archival.get(reference.file_id)).archive_state is ArchiveState.ARCHIVAL_PENDING

            dataset = await uow.repositories.datasets.get(dataset_id=dataset_id)
            assert dataset.study == study_id
            assert dataset.references == [reference_id]
            for r in dataset.records:
                assert r.references == [reference_id]
                assert r.value is None
                # code 0 marks a curve not replicated, so it is not migrated
                assert not r.groups

        dataset = await uow.repositories.datasets.get(dataset_id=ids.datasets[key_a][1])
        assert sorted(r.unit for r in dataset.records) == sorted(units.values())
        for r in dataset.records:
            assert (r.start, r.end) == (datetime64('2019-05-20'), datetime64('2019-05-20'))
        loaded = await uow.repositories.datasets.get(dataset_id=ids.datasets[key_b][1])
        assert [r.unit for r in loaded.records] == [units['34_T1']]

        # Joined the scope of the other dataset of submission A
        program = await uow.repositories.programs.get(study_id=study_id)
        scopes = [set(s.dataset_ids) for s in program.get_study(study_id).get_grouping(grouping_id=replicate).dataset_scopes]
        other = next(iter(curves_context['datasets'].datasets.values()))
        assert {other, ids.datasets[key_a][1]} in scopes

    again = await prepare(uow_factory, curves_context)
    assert again.created == 0
    assert again.datasets == ids.datasets
