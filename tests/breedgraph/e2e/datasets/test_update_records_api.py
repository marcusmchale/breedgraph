"""
Record updates through GraphQL, on the read-policy scenario and its spectra (tests/breedgraph/scenarios/spectra_scenario.py).
An update gives only what changes: its start, end and value are optional, as in RecordUpdate, and a start or end
given as null is removed. A record on a complex scale has the files it cites replaced, but is never left citing none:
that is refused for the record, as an item error of the submission, and the record keeps its file. Removing the record
is how its last file goes.
"""
import pytest

from tests.breedgraph.e2e.datasets.submissions import result_as, processed
from tests.breedgraph.scenarios.spectra_scenario import RECORDS, READ_ON

UPDATE = "mutation ($d: DatasetUpdate!) { datasetsUpdate(dataset: $d) { status result errors { name message } } }"
RECORDS_OF = (
    "query ($ids: [ID!]) { datasets(ids: $ids) { status result { records { id value start end unit { id } references { id } } } "
    "errors { name message } } }"
)


async def update(client, login_token_factory, read_policy, dataset_id: int, record: dict) -> dict:
    """Update the record as the writer, who curates it, and return the submission once processed"""
    submission_id = await result_as(
        client, login_token_factory, read_policy, 'writer', 'datasetsUpdate', UPDATE, {'d': {'id': dataset_id, 'records': [record]}}
    )
    return await processed(client, login_token_factory, read_policy, 'writer', submission_id)


async def records_of(client, login_token_factory, read_policy, dataset_id: int) -> list[dict]:
    (dataset,) = await result_as(client, login_token_factory, read_policy, 'writer', 'datasets', RECORDS_OF, {'ids': [dataset_id]})
    return dataset['records']


async def record_of(client, login_token_factory, read_policy, dataset_id: int, record_id: int) -> dict:
    return next(
        record for record in await records_of(client, login_token_factory, read_policy, dataset_id)
        if int(record['id']) == record_id
    )


def cited(record: dict) -> list[int]:
    return [int(reference['id']) for reference in record['references']]


@pytest.mark.asyncio(loop_scope="session")
async def test_an_update_leaving_a_record_citing_no_file_is_refused(client, login_token_factory, read_policy, spectra):
    record_id = spectra.records['tree_public']
    # as curation sends it, with its start and no value
    submission = await update(client, login_token_factory, read_policy, spectra.ids['dataset'], {
        'id': record_id, 'start': READ_ON, 'end': None, 'value': None, 'referenceIds': []
    })
    assert submission['status'] == 'FAILED'
    assert submission['itemErrors'] == [
        {'index': 0, 'error': "Complex scale records require at least one reference: remove the record instead"}
    ]
    assert cited(await record_of(client, login_token_factory, read_policy, spectra.ids['dataset'], record_id)) == [
        spectra.references[name] for name in RECORDS['tree_public']
    ]


@pytest.mark.asyncio(loop_scope="session")
async def test_an_update_replaces_the_files_a_record_cites(client, login_token_factory, read_policy, spectra):
    record_id = spectra.records['tree_public']
    other = spectra.references["Readpolicy canopy spectrum 2"]
    submission = await update(client, login_token_factory, read_policy, spectra.ids['dataset'], {
        'id': record_id, 'start': READ_ON, 'end': None, 'value': None, 'referenceIds': [other]
    })
    assert submission['status'] == 'COMPLETED', submission
    assert cited(await record_of(client, login_token_factory, read_policy, spectra.ids['dataset'], record_id)) == [other]


@pytest.mark.asyncio(loop_scope="session")
async def test_an_update_giving_only_files_leaves_the_rest(client, login_token_factory, read_policy, spectra):
    record_id = spectra.records['tree_registered']
    other = spectra.references["Readpolicy canopy spectrum 1"]
    submission = await update(client, login_token_factory, read_policy, spectra.ids['dataset'], {
        'id': record_id, 'referenceIds': [other]
    })
    assert submission['status'] == 'COMPLETED', submission
    record = await record_of(client, login_token_factory, read_policy, spectra.ids['dataset'], record_id)
    assert (cited(record), record['start']) == ([other], READ_ON)


@pytest.mark.asyncio(loop_scope="session")
async def test_an_update_giving_only_a_value_leaves_the_rest(client, login_token_factory, read_policy):
    dataset_id = read_policy['dataset_public']
    record = next(
        record for record in await records_of(client, login_token_factory, read_policy, dataset_id)
        if int(record['unit']['id']) == read_policy['tree_public']
    )
    submission = await update(client, login_token_factory, read_policy, dataset_id, {'id': record['id'], 'value': '9'})
    assert submission['status'] == 'COMPLETED', submission
    assert await record_of(client, login_token_factory, read_policy, dataset_id, int(record['id'])) == {**record, 'value': '9'}


@pytest.mark.asyncio(loop_scope="session")
async def test_an_update_giving_a_time_as_null_removes_it(client, login_token_factory, read_policy, spectra):
    record_id, dataset_id = spectra.records['tree_registered'], spectra.ids['dataset']
    submission = await update(client, login_token_factory, read_policy, dataset_id, {'id': record_id, 'end': '2025-06-30'})
    assert submission['status'] == 'COMPLETED', submission
    submission = await update(client, login_token_factory, read_policy, dataset_id, {'id': record_id, 'start': None})
    assert submission['status'] == 'COMPLETED', submission
    record = await record_of(client, login_token_factory, read_policy, dataset_id, record_id)
    assert (record['start'], record['end']) == (None, '2025-06-30')
