import pytest
import asyncio

from breedgraph.domain.model.submissions import SubmissionStatus

from tests.e2e.datasets.post_methods import (
    post_to_submit_records,
    post_to_get_datasets,
    post_to_get_dataset_submission
)

from tests.e2e.utils import get_verified_payload, assert_payload_success


@pytest.mark.asyncio(loop_scope="session")
async def test_create_dataset_with_records(
        dataset_build_context,
        login_token_factory,
        client
):
    user_id = dataset_build_context['user_id']
    login_token = login_token_factory(user_id)
    concept_id = dataset_build_context['concept_id']
    study_id = dataset_build_context['study_id']
    unit_id = dataset_build_context['unit_id']
    response = await post_to_submit_records(
        client,
        login_token,
        dataset = {
            "conceptId":concept_id,
            "studyId":study_id,
            'records':[
                {
                    'unitId': unit_id,
                    'value': '100',
                    'start': "2022-10-10"
                }
            ]
        }
    )
    payload = get_verified_payload(response, "datasetsSubmitRecords")
    submission_id = payload['result']
    assert submission_id
    limit = 10
    while True:
        limit -=1
        if limit == 0:
            raise TimeoutError("Getting submission timed out")

        await asyncio.sleep(0.1)
        submission_response = await post_to_get_dataset_submission(
            client,
            login_token,
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


# Todo add test with bad records, remove records,update records
#