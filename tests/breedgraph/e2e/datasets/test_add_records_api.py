"""
datasetsAddRecords, on the read-policy scenario and its spectra (tests/breedgraph/scenarios/spectra_scenario.py):
records are added to a stored dataset as a new dataset's are, parsed with its scale and checked against its study's
groupings, on units the writer can read. One that doesn't parse is an item error of the submission, which then adds
none of them; one on a unit the writer can't read, or that isn't there, fails it as not found.
"""
import pytest

from tests.breedgraph.e2e.datasets.submissions import result_as, processed

ADD = (
    "mutation ($id: ID!, $records: [RecordInput!]) { datasetsAddRecords(id: $id, records: $records) "
    "{ status result errors { name message } } }"
)
RECORDS = (
    "query ($ids: [ID!]) { datasets(ids: $ids) { status result { "
    "records { value start unit { id } groups { id code } references { id } } } errors { name message } } }"
)
GROUPINGS = "query ($id: ID!) { programsStudy(id: $id) { status result { groupings { id name } } errors { name message } } }"


async def add(client, login_token_factory, read_policy, dataset_id: int, records: list[dict]) -> dict:
    """Add the records to the dataset as the writer, who curates it, and return the submission once processed"""
    submission_id = await result_as(
        client, login_token_factory, read_policy, 'writer', 'datasetsAddRecords', ADD, {'id': dataset_id, 'records': records}
    )
    return await processed(client, login_token_factory, read_policy, 'writer', submission_id)


async def records_of(client, login_token_factory, read_policy, dataset_id: int) -> list[dict]:
    (dataset,) = await result_as(client, login_token_factory, read_policy, 'writer', 'datasets', RECORDS, {'ids': [dataset_id]})
    return dataset['records']


@pytest.mark.asyncio(loop_scope="session")
async def test_a_record_is_added_with_its_code(client, login_token_factory, read_policy):
    study = await result_as(
        client, login_token_factory, read_policy, 'writer', 'programsStudy', GROUPINGS, {'id': read_policy['study_public']}
    )
    batch = next(grouping['id'] for grouping in study['groupings'] if grouping['name'] == 'Study Scoped Batch')
    dataset_id = read_policy['dataset_public']
    before = await records_of(client, login_token_factory, read_policy, dataset_id)
    submission = await add(client, login_token_factory, read_policy, dataset_id, [
        {'unitId': read_policy['tree_registered'], 'value': '7', 'start': '2025-01-02', 'groups': [{'id': batch, 'code': 'Batch 1'}]}
    ])
    assert submission['status'] == 'COMPLETED', submission
    assert [record for record in await records_of(client, login_token_factory, read_policy, dataset_id) if record not in before] == [{
        'value': '7', 'start': '2025-01-02', 'unit': {'id': str(read_policy['tree_registered'])},
        'groups': [{'id': batch, 'code': 'Batch 1'}], 'references': []
    }]


@pytest.mark.asyncio(loop_scope="session")
async def test_a_record_that_does_not_parse_adds_none(client, login_token_factory, read_policy):
    dataset_id = read_policy['dataset_public']
    before = await records_of(client, login_token_factory, read_policy, dataset_id)
    submission = await add(client, login_token_factory, read_policy, dataset_id, [
        {'unitId': read_policy['tree_public'], 'value': '8'},
        {'unitId': read_policy['tree_public'], 'value': 'tall'},
    ])
    assert submission['status'] == 'FAILED'
    assert [item['index'] for item in submission['itemErrors']] == [1]
    assert await records_of(client, login_token_factory, read_policy, dataset_id) == before


@pytest.mark.asyncio(loop_scope="session")
async def test_a_record_on_a_complex_scale_is_added_citing_its_file(client, login_token_factory, read_policy, spectra):
    file = spectra.references["Readpolicy canopy spectrum 2"]
    submission = await add(client, login_token_factory, read_policy, spectra.ids['dataset'], [
        {'unitId': read_policy['tree_registered'], 'start': '2025-07-01', 'referenceIds': [file]}
    ])
    assert submission['status'] == 'COMPLETED', submission
    assert {
        'value': None, 'start': '2025-07-01', 'unit': {'id': str(read_policy['tree_registered'])}, 'groups': [],
        'references': [{'id': str(file)}]
    } in await records_of(client, login_token_factory, read_policy, spectra.ids['dataset'])


@pytest.mark.asyncio(loop_scope="session")
async def test_a_record_on_a_complex_scale_citing_no_file_is_refused(client, login_token_factory, read_policy, spectra):
    before = await records_of(client, login_token_factory, read_policy, spectra.ids['dataset'])
    submission = await add(client, login_token_factory, read_policy, spectra.ids['dataset'], [
        {'unitId': read_policy['tree_registered'], 'value': '0.5'}
    ])
    assert submission['status'] == 'FAILED'
    assert submission['itemErrors'] == [{'index': 0, 'error': "Complex scale records require at least one reference"}]
    assert await records_of(client, login_token_factory, read_policy, spectra.ids['dataset']) == before


@pytest.mark.asyncio(loop_scope="session")
@pytest.mark.parametrize('unit', ['leaf_other', None])
async def test_a_record_on_a_unit_the_writer_cannot_read_is_not_added(client, login_token_factory, read_policy, unit):
    """Another team's private unit is not found, as is a unit that isn't there"""
    unit_id = read_policy[unit] if unit else 10 ** 6
    dataset_id = read_policy['dataset_public']
    before = await records_of(client, login_token_factory, read_policy, dataset_id)
    submission = await add(client, login_token_factory, read_policy, dataset_id, [
        {'unitId': read_policy['tree_public'], 'value': '6'}, {'unitId': unit_id, 'value': '6'}
    ])
    assert submission['status'] == 'FAILED'
    assert any(f"Unit {unit_id} was not found" in error for error in submission['errors']), submission['errors']
    assert await records_of(client, login_token_factory, read_policy, dataset_id) == before
