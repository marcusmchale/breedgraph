import asyncio

import pytest

from breedgraph.domain.model.submissions import SubmissionStatus
from tests.breedgraph.e2e.analysis.post_methods import (
    post_to_submit_analysis, post_to_get_analysis_submission, post_to_get_dataset_submission_id, worker_headers,
    post_to_get_recent_analysis_submissions
)
from tests.breedgraph.e2e.datasets.post_methods import post_to_create_dataset
from tests.breedgraph.e2e.utils import get_verified_payload, assert_payload_success


async def wait_for_status(get, statuses: set[SubmissionStatus], limit=20):
    for _ in range(limit):
        await asyncio.sleep(0.1)
        result = await get()
        if SubmissionStatus[result['status']] in statuses:
            return result
    raise TimeoutError("Waiting for status timed out")


async def create_dataset(client, login_token, context) -> int:
    response = await post_to_create_dataset(
        client,
        login_token,
        dataset={
            "conceptId": context['concept_id'],
            "studyId": context['study_id'],
            "records": [
                {'unitId': context['unit_id'], 'value': '100', 'start': "2020-06-01"},
                {'unitId': context['unit_id'], 'value': '120', 'start': "2021-06-01"},
            ]
        },
        control_team_id=context['team_id']
    )
    submission_id = get_verified_payload(response, "datasetsCreate")['result']

    async def get():
        response = await post_to_get_dataset_submission_id(client, login_token, submission_id=submission_id)
        payload = get_verified_payload(response, "datasetsSubmission")
        assert_payload_success(payload)
        return payload['result']

    submission = await wait_for_status(get, {SubmissionStatus.COMPLETED, SubmissionStatus.FAILED})
    assert submission['status'] == SubmissionStatus.COMPLETED.name, submission['errors']
    return int(submission['datasetId'])


def descriptive_analysis(dataset_id, concept_id) -> dict:
    return {
        "analysisType": "DESCRIPTIVE_STATISTICS",
        "name": "Height by year",
        "datasetIds": [dataset_id],
        "exclusions": [{"unitIds": [0]}],
        "descriptiveStatistics": {
            "terms": [
                {"reference": {"type": "CONCEPT", "conceptId": concept_id}},
                {"reference": {"type": "TIME"}}
            ],
            "grouping": {
                "time": {
                    "assignment": "START",
                    "binning": {"boundaries": ["2021-01-01"], "labels": ["2020", "2021"], "boundary": "RIGHT"}
                }
            }
        }
    }


@pytest.mark.asyncio(loop_scope="session")
async def test_invalid_analysis_rejected_with_paths(dataset_build_context, login_token_factory, client):
    login_token = login_token_factory(dataset_build_context['user_id'])
    analysis = descriptive_analysis(1, dataset_build_context['concept_id'])
    analysis['descriptiveStatistics']['grouping'] = {}
    response = await post_to_submit_analysis(client, login_token, analysis)
    payload = get_verified_payload(response, "analysisSubmit")
    assert payload['status'] == 'ERROR'
    assert payload['result'] is None
    assert {(e['name'], tuple(e['path'])) for e in payload['errors']} == {
        ('CONFIG_INVALID', ('descriptiveStatistics', 'terms', '1', 'reference', 'type'))
    }


@pytest.mark.asyncio(loop_scope="session")
async def test_analysis_queued_and_completed_by_worker(dataset_build_context, login_token_factory, client):
    login_token = login_token_factory(dataset_build_context['user_id'])
    dataset_id = await create_dataset(client, login_token, dataset_build_context)

    analysis = descriptive_analysis(dataset_id, dataset_build_context['concept_id'])
    payload = get_verified_payload(await post_to_submit_analysis(client, login_token, analysis), "analysisSubmit")
    assert_payload_success(payload)
    analysis_id = payload['result']

    recent = get_verified_payload(
        await post_to_get_recent_analysis_submissions(client, login_token), "analysisRecentSubmissions"
    )
    assert_payload_success(recent)
    assert analysis_id in recent['result']

    async def get():
        response = await post_to_get_analysis_submission(client, login_token, analysis_id)
        payload = get_verified_payload(response, "analysisSubmission")
        assert_payload_success(payload)
        return payload['result']

    submission = await wait_for_status(get, {SubmissionStatus.QUEUED, SubmissionStatus.FAILED})
    assert submission['status'] == SubmissionStatus.QUEUED.name, submission['errors']
    assert submission['id'] == analysis_id
    assert submission['name'] == "Height by year"
    assert submission['analysisType'] == "DESCRIPTIVE_STATISTICS"
    assert submission['exclusions'] == [{'unitIds': ['0'], 'start': None, 'end': None}]
    assert submission['config']['terms'][1] == {'reference': {'type': 'TIME', 'conceptId': None}, 'transformations': []}
    assert submission['config']['interactions'] == []

    # the worker endpoints require the service token
    assert (await client.get("/analysis_jobs/next")).status_code == 401

    response = await client.get("/analysis_jobs/next", headers=worker_headers())
    assert response.status_code == 200
    job = response.json()
    assert job['analysis_id'] == analysis_id
    job_payload = job['payload']
    assert job_payload['analysis_type'] == 'DESCRIPTIVE_STATISTICS'
    assert [c['name'] for c in job_payload['columns']] == [f"concept:{dataset_build_context['concept_id']}", 'time']
    assert job_payload['rows'] == [[100.0, '2020'], [120.0, '2021']]
    assert [o['group']['time'] for o in job_payload['observations']] == ['2020', '2021']
    assert (await client.get("/analysis_jobs/next", headers=worker_headers())).status_code == 204

    result = {
        'lease': job['lease'],
        'analysis_id': analysis_id,
        'analysis_type': 'DESCRIPTIVE_STATISTICS',
        'result': {'terms': [{'count': 2}], 'estimated_means': []},
        'warnings': [{'code': 'SINGLE_LEVEL_TERM', 'message': 'test'}]
    }
    wrong_type = result | {'analysis_type': 'ANOVA'}
    assert (await client.post(f"/analysis_jobs/{analysis_id}/result", json=wrong_type, headers=worker_headers())).status_code == 422
    response = await client.post(f"/analysis_jobs/{analysis_id}/result", json=result, headers=worker_headers())
    assert response.status_code == 204

    submission = await get()
    assert submission['status'] == SubmissionStatus.COMPLETED.name
    assert submission['result'] == {'analysisId': analysis_id, 'terms': [{'count': 2}]}
    assert submission['errors'] == []
    warning_codes = [w['code'] for w in submission['warnings']]
    assert warning_codes == ['EXCLUDED_BY_CONFIG', 'SINGLE_LEVEL_TERM']
