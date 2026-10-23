"""
datasetsCreate, on the read-policy scenario: a new dataset's records are on units the writer can read. One on another
team's private unit, or on a unit that isn't there, is not found, and nothing is created.
"""
import asyncio

import pytest

from breedgraph.domain.model.controls import Access
from breedgraph.entrypoints.fastapi.graphql.decorators import GQLStatus

from tests.breedgraph.e2e.datasets.submissions import result_as, processed, SUBMISSION
from tests.breedgraph.e2e.utils import post_as, get_verified_payload
from tests.breedgraph.scenarios.account_builder import AccountBuilder
from tests.breedgraph.scenarios.authorisation_manager import AuthorisationManager

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


@pytest.mark.asyncio(loop_scope="session")
async def test_a_writer_without_curate_access_creates_a_dataset(client, login_token_factory, read_policy, uow_factory):
    """
    Creating a dataset, records and all, needs write access to the team that will control it, not curate access:
    adding records to a dataset that exists is a change, but these are part of creating it
    """
    user_id = await AccountBuilder(uow_factory).account()
    for access in (Access.READ, Access.WRITE):
        await AuthorisationManager(uow_factory).authorise_affiliation(
            agent_id=read_policy['admin'], user_id=user_id, team_id=read_policy['child'], access=access
        )

    async def result(operation: str, text: str, variables: dict):
        payload = get_verified_payload(await post_as(client, login_token_factory, user_id, text, variables), operation)
        assert payload['status'] == GQLStatus.SUCCESS.name, payload['errors']
        return payload['result']

    submission_id = await result('datasetsCreate', CREATE, {
        'd': {
            'studyId': read_policy['study_public'],
            'conceptId': read_policy['ontology_variable_height'],
            'records': [{'unitId': read_policy['tree_public'], 'value': '7'}]
        },
        'team': read_policy['child']
    })
    for _ in range(50):
        await asyncio.sleep(0.1)
        submission = await result('datasetsSubmission', SUBMISSION, {'id': submission_id})
        if submission['status'] in ('COMPLETED', 'FAILED'):
            break
    assert submission['status'] == 'COMPLETED', submission
