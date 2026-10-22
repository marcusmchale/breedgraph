"""
Records on a complex scale through GraphQL, on the spectra (tests/breedgraph/scenarios/spectra_scenario.py): an update
replaces the files a record cites, but can't leave it citing none. That is refused for the record, as an item error of
the submission, and the record keeps its file: removing the record is how its last file goes.
"""
import pytest

from tests.breedgraph.e2e.datasets.submissions import result_as, processed
from tests.breedgraph.scenarios.spectra_scenario import RECORDS, READ_ON

UPDATE = "mutation ($d: DatasetUpdate!) { datasetsUpdate(dataset: $d) { status result errors { name message } } }"
CITED = "query ($ids: [ID!]) { datasets(ids: $ids) { status result { records { id references { id } } } errors { name message } } }"


async def update(client, login_token_factory, read_policy, spectra, unit: str, reference_ids: list[int]) -> dict:
    """
    Update the unit's record to cite the references, as curation does (with its start, and no value), and return the
    submission once processed
    """
    submission_id = await result_as(client, login_token_factory, read_policy, 'writer', 'datasetsUpdate', UPDATE, {'d': {
        'id': spectra.ids['dataset'],
        'records': [{'id': spectra.records[unit], 'start': READ_ON, 'end': None, 'value': None, 'referenceIds': reference_ids}]
    }})
    return await processed(client, login_token_factory, read_policy, 'writer', submission_id)


async def cited(client, login_token_factory, read_policy, spectra, unit: str) -> list[int]:
    (dataset,) = await result_as(client, login_token_factory, read_policy, 'writer', 'datasets', CITED, {'ids': [spectra.ids['dataset']]})
    record = next(record for record in dataset['records'] if int(record['id']) == spectra.records[unit])
    return [int(reference['id']) for reference in record['references']]


@pytest.mark.asyncio(loop_scope="session")
async def test_an_update_leaving_a_record_citing_no_file_is_refused(client, login_token_factory, read_policy, spectra):
    submission = await update(client, login_token_factory, read_policy, spectra, 'tree_public', [])
    assert submission['status'] == 'FAILED'
    assert submission['itemErrors'] == [
        {'index': 0, 'error': "Complex scale records require at least one reference: remove the record instead"}
    ]
    assert await cited(client, login_token_factory, read_policy, spectra, 'tree_public') == [
        spectra.references[name] for name in RECORDS['tree_public']
    ]


@pytest.mark.asyncio(loop_scope="session")
async def test_an_update_replaces_the_files_a_record_cites(client, login_token_factory, read_policy, spectra):
    other = spectra.references["Readpolicy canopy spectrum 2"]
    submission = await update(client, login_token_factory, read_policy, spectra, 'tree_public', [other])
    assert submission['status'] == 'COMPLETED', submission
    assert await cited(client, login_token_factory, read_policy, spectra, 'tree_public') == [other]
