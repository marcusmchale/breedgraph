"""
The spectra of the test database (tests/breedgraph/scenarios/spectra_scenario.py), on the read-policy scenario: records
of the canopy spectrum, a variable published on a complex scale, which cite data files rather than hold values, and
which only the child team reads
"""
from pathlib import Path

import pytest

from breedgraph.config import FILE_STORAGE_PATH
from breedgraph.domain.model.ontology import ScaleType, LifecyclePhase
from breedgraph.domain.model.references import ReferenceType, DataFormat

from tests.breedgraph.scenarios.ontology_builder import CANOPY_SPECTRUM
from tests.breedgraph.scenarios.spectra_scenario import FILES, RECORDS, READ_ON

REDACTED = 'REDACTED'


@pytest.mark.asyncio(loop_scope="session")
async def test_the_variable_is_published_on_a_complex_scale(read_policy, views_factory):
    variable_id, scale_id = read_policy['ontology_variable_spectrum'], read_policy['ontology_scale_spectrum']
    async with views_factory.get_views(user_id=None) as views:
        entries = {entry.id: entry for entry in await views.ontology.get_entries(entry_ids=[variable_id, scale_id])}
    variable, scale = entries[variable_id], entries[scale_id]
    assert (variable.name, variable.phase, variable.scale) == (CANOPY_SPECTRUM, LifecyclePhase.ACTIVE, scale_id)
    assert (scale.scale_type, scale.phase) == (ScaleType.COMPLEX, LifecyclePhase.ACTIVE)


@pytest.mark.asyncio(loop_scope="session")
async def test_the_records_cite_files_and_hold_no_values(read_policy, spectra, views_factory):
    async with views_factory.get_views(user_id=read_policy['writer']) as views:
        (dataset,) = await views.datasets.get_datasets(dataset_ids=[spectra.ids['dataset']])
        records = await views.datasets.get_records(spectra.ids['dataset'])
    assert (dataset.study, dataset.concept) == (spectra.ids['study'], read_policy['ontology_variable_spectrum'])
    assert {record['id']: (record['unit'], record['value'], str(record['start']), record['references']) for record in records} == {
        spectra.records[unit]: (read_policy[unit], None, READ_ON, [spectra.references[name] for name in names])
        for unit, names in RECORDS.items()
    }


@pytest.mark.asyncio(loop_scope="session")
async def test_the_files_are_csv_data_files_in_the_store(read_policy, spectra, views_factory):
    async with views_factory.get_views(user_id=read_policy['writer']) as views:
        references = {reference.id: reference for reference in await views.references.get_references(list(spectra.references.values()))}
    for name, (filename, content) in FILES.items():
        reference = references[spectra.references[name]]
        file_id = spectra.files[name][0]
        assert (reference.type, reference.description, reference.filename, reference.format, reference.file_id) == (
            ReferenceType.DATA_FILE, name, filename, DataFormat.CSV, file_id
        )
        assert Path(FILE_STORAGE_PATH, file_id).read_bytes() == content


@pytest.mark.asyncio(loop_scope="session")
@pytest.mark.parametrize('viewer, readable', [
    ('admin', True), ('writer', True), ('stranger', False), ('outsider', False), ('anonymous', False)
])
async def test_only_the_child_team_reads_them(read_policy, spectra, views_factory, viewer, readable):
    async with views_factory.get_views(user_id=read_policy.user(viewer)) as views:
        (dataset,) = await views.datasets.get_datasets(dataset_ids=[spectra.ids['dataset']])
        references = await views.references.get_references(list(spectra.references.values()))
    assert dataset.redacted is not readable
    # hidden files asked for by id are placeholders
    assert {reference.description for reference in references} == (set(FILES) if readable else {REDACTED})
