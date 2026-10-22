"""
datasetsCreate, on the read-policy scenario: a new dataset's records are on units the writer can read. One on another
team's private unit, or on a unit that isn't there, is not found, and nothing is created.
"""
import pytest

from tests.breedgraph.e2e.datasets.submissions import result_as, processed

CREATE = (
    "mutation ($d: DatasetInput!, $team: ID!) { datasetsCreate(dataset: $d, controlTeamId: $team) "
    "{ status result errors { name message } } }"
)
DATASETS = (
    "query ($studies: [ID!], $concepts: [ID!]) { datasets(studyIds: $studies, conceptIds: $concepts) { status result { "
    "id records { value unit { id } } } errors { name message } } }"
)


async def create(client, login_token_factory, read_policy, unit_ids: list[int]) -> dict:
    """A height dataset of study_public, created by the writer with a record of 5 on each unit, once processed"""
    submission_id = await result_as(client, login_token_factory, read_policy, 'writer', 'datasetsCreate', CREATE, {
        'd': {
            'studyId': read_policy['study_public'],
            'conceptId': read_policy['ontology_variable_height'],
            'records': [{'unitId': unit_id, 'value': '5'} for unit_id in unit_ids]
        },
        'team': read_policy['child']
    })
    return await processed(client, login_token_factory, read_policy, 'writer', submission_id)


async def datasets_by_id(client, login_token_factory, read_policy) -> dict[str, dict]:
    """The study's height datasets the writer reads, by id"""
    result = await result_as(client, login_token_factory, read_policy, 'writer', 'datasets', DATASETS, {
        'studies': [read_policy['study_public']], 'concepts': [read_policy['ontology_variable_height']]
    })
    return {dataset['id']: dataset for dataset in result}


@pytest.mark.asyncio(loop_scope="session")
async def test_a_dataset_is_created_with_records_on_units_the_writer_reads(client, login_token_factory, read_policy):
    before = await datasets_by_id(client, login_token_factory, read_policy)
    submission = await create(client, login_token_factory, read_policy, [read_policy['tree_public'], read_policy['leaf_private']])
    assert submission['status'] == 'COMPLETED', submission
    created = [dataset for dataset_id, dataset in (await datasets_by_id(client, login_token_factory, read_policy)).items() if dataset_id not in before]
    assert [sorted(int(record['unit']['id']) for record in dataset['records']) for dataset in created] == [
        sorted([read_policy['tree_public'], read_policy['leaf_private']])
    ]


@pytest.mark.asyncio(loop_scope="session")
@pytest.mark.parametrize('unit', ['leaf_other', None])
async def test_a_record_on_a_unit_the_writer_cannot_read_creates_nothing(client, login_token_factory, read_policy, unit):
    """Another team's private unit is not found, as is a unit that isn't there"""
    unit_id = read_policy[unit] if unit else 10 ** 6
    before = await datasets_by_id(client, login_token_factory, read_policy)
    submission = await create(client, login_token_factory, read_policy, [read_policy['tree_public'], unit_id])
    assert submission['status'] == 'FAILED'
    assert any(f"Unit {unit_id} was not found" in error for error in submission['errors']), submission['errors']
    assert await datasets_by_id(client, login_token_factory, read_policy) == before
