"""
Dataset submissions through GraphQL, as a viewer of the read-policy scenario: datasetsCreate, datasetsUpdate and
datasetsAddRecords answer with a submission id, and the submission is processed in the background
"""
import asyncio

import pytest

from breedgraph.entrypoints.fastapi.graphql.decorators import GQLStatus

from tests.breedgraph.e2e.utils import post_as, get_verified_payload

SUBMISSION = (
    "query ($id: ID!) { datasetsSubmission(id: $id) { status result { status errors itemErrors { index error } } "
    "errors { name message } } }"
)


async def result_as(client, login_token_factory, read_policy, viewer: str, operation: str, text: str, variables: dict):
    """The operation's result, as the viewer, which must succeed"""
    response = await post_as(client, login_token_factory, read_policy.user(viewer), text, variables)
    payload = get_verified_payload(response, operation)
    assert payload['status'] == GQLStatus.SUCCESS.name, payload['errors']
    return payload['result']


async def processed(client, login_token_factory, read_policy, viewer: str, submission_id: str) -> dict:
    """The submission once processed: its status, COMPLETED or FAILED, its errors and its item errors"""
    for _ in range(50):
        await asyncio.sleep(0.1)
        submission = await result_as(client, login_token_factory, read_policy, viewer, 'datasetsSubmission', SUBMISSION, {'id': submission_id})
        if submission['status'] in ('COMPLETED', 'FAILED'):
            return submission
    pytest.fail(f"Submission {submission_id} was not processed")
