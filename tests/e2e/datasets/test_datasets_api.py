import pytest
import asyncio

from src.breedgraph.domain.model.ontology import OntologyEntryLabel
from src.breedgraph.domain.model.submissions import SubmissionStatus
from tests.e2e.conftest import first_user_login_token
from tests.e2e.datasets.post_methods import (
    post_to_create_dataset,
    post_to_get_datasets,
    post_to_add_records,
    post_to_get_dataset_submission, post_to_add_records
)
from tests.e2e.ontologies.post_methods import post_to_get_entries
from tests.e2e.utils import get_verified_payload, assert_payload_success

@pytest.mark.usefixtures("session_database")
@pytest.mark.asyncio(scope="session")
async def test_create_dataset(
        client,
        first_user_login_token,
        first_account_with_all_affiliations,
        basic_ontology
):
    variable_response = await post_to_get_entries(
        client,
        token=first_user_login_token,
        labels=[OntologyEntryLabel.VARIABLE]
    )
    variable_payload = get_verified_payload(variable_response, "ontologyEntries")
    variable_id = variable_payload.get('result')[0].get('id')
    response = await post_to_create_dataset(
        client,
        first_user_login_token,
        dataset = {
            "conceptId":variable_id
        }
    )
    payload = get_verified_payload(response, "datasetsCreateDataset")
    submission_id = payload['result']
    assert submission_id

    while True:
        await asyncio.sleep(0.1)
        submission_response = await post_to_get_dataset_submission(
            client,
            first_user_login_token,
            submission_id = submission_id
        )
        submission_payload = get_verified_payload(submission_response, "datasetsSubmission")
        assert_payload_success(submission_payload)
        status = SubmissionStatus[submission_payload.get('result').get('status')]
        if status == SubmissionStatus.COMPLETED:
            break
        elif status == SubmissionStatus.FAILED:
            pytest.fail(f"Dataset submission failed with status: {status}")
        elif status in [SubmissionStatus.PENDING, SubmissionStatus.PROCESSING]:
            continue
        else:
            pytest.fail(f"Unexpected submission status: {status}")

@pytest.mark.usefixtures("session_database")
@pytest.mark.asyncio(scope="session")
async def test_create_dataset_with_records(
        client,
        first_user_login_token,
        first_account_with_all_affiliations,
        basic_ontology,
        basic_block
):
    variable_response = await post_to_get_entries(
        client,
        token=first_user_login_token,
        labels=[OntologyEntryLabel.VARIABLE]
    )
    variable_payload = get_verified_payload(variable_response, "ontologyEntries")
    variable_id = variable_payload.get('result')[0].get('id')
    response = await post_to_create_dataset(
        client,
        first_user_login_token,
        dataset = {
            "conceptId":variable_id,
            'records':[
                {
                    'unitId': basic_block.get_root_id(),
                    'value': '100',
                    'start': "2022-10-10"
                }
            ]
        }
    )
    payload = get_verified_payload(response, "datasetsCreateDataset")
    submission_id = payload['result']
    assert submission_id

    while True:
        await asyncio.sleep(0.1)
        submission_response = await post_to_get_dataset_submission(
            client,
            first_user_login_token,
            submission_id=submission_id
        )
        submission_payload = get_verified_payload(submission_response, "datasetsSubmission")
        assert_payload_success(submission_payload)
        status = SubmissionStatus[submission_payload.get('result').get('status')]
        if status == SubmissionStatus.COMPLETED:
            break
        elif status == SubmissionStatus.FAILED:
            pytest.fail(f"Dataset submission failed with status: {status}")
        elif status in [SubmissionStatus.PENDING, SubmissionStatus.PROCESSING]:
            continue
        else:
            pytest.fail(f"Unexpected submission status: {status}")



@pytest.mark.asyncio(scope="session")
async def test_extend_dataset(
        client,
        first_user_login_token,
        first_account_with_all_affiliations,
        basic_ontology,
        basic_block
):
    datasets_response = await post_to_get_datasets(
        client,
        token=first_user_login_token,
        dataset_id=None,
        concept_id=None
    )
    datasets_payload = get_verified_payload(datasets_response, 'datasets')

    dataset_id = datasets_payload.get('result')[0].get('id')
    add_record_response = await post_to_add_records(
        client,
        token=first_user_login_token,
        dataset_id = dataset_id,
        records = [
                {
                    'unitId': basic_block.get_root_id(),
                    'value': '200',
                    'start': "2023-10-10"
                }
            ]
    )
    add_record_payload = get_verified_payload(add_record_response, "datasetsAddRecords")
    assert_payload_success(add_record_payload)

# Todo add test with bad records, remove records, also update dataset
#