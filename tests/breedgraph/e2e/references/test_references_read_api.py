"""
The reference queries and file downloads under the read policy, through GraphQL, on the read-policy scenario
(see tests/breedgraph/integration/views/test_references_view.py for the view underneath).

A file downloads for anyone who can read its reference, anonymous users included for public files, and is refused
otherwise. A reference cited by a study is a placeholder of the right type where the viewer cannot read it.
"""
import pytest

from breedgraph.entrypoints.fastapi.graphql.decorators import GQLStatus

from tests.breedgraph.e2e.utils import post_as, get_verified_payload
from tests.breedgraph.scenarios.read_policy_scenario import VIEWERS, REFERENCES, STUDY_REFERENCES

REDACTED = 'REDACTED'
TYPENAMES = {'FILE': 'FileReference', 'LEGAL': 'LegalReference'}

REFERENCE_FIELDS = (
    "__typename id description "
    "... on FileReference { fileId filename } "
    "... on LegalReference { text }"
)


async def payload_of(client, login_token_factory, read_policy, viewer: str, operation: str, text: str, variables=None):
    response = await post_as(client, login_token_factory, read_policy.user(viewer), text, variables)
    return get_verified_payload(response, operation)


async def result_of(client, login_token_factory, read_policy, viewer: str, operation: str, text: str, variables=None):
    payload = await payload_of(client, login_token_factory, read_policy, viewer, operation, text, variables)
    # an empty list is a valid result here, so not assert_payload_success
    assert payload['status'] == GQLStatus.SUCCESS.name, payload['errors']
    assert payload['errors'] is None
    return payload['result']


def assert_reference(read_policy, viewer: str, name: str, reference: dict):
    reference_type, description = REFERENCES[name]
    assert int(reference['id']) == read_policy[name]
    assert reference['__typename'] == TYPENAMES[reference_type]
    if read_policy.readable(viewer, name):
        assert reference['description'] == description
        if reference_type == 'FILE':
            assert reference['fileId'] == read_policy.files[name][0]
    else:
        assert reference['description'] == REDACTED
        if reference_type == 'FILE':
            assert reference['fileId'] is None
            assert reference['filename'] is None
        else:
            assert reference['text'] in (None, REDACTED)


@pytest.mark.asyncio(loop_scope="session")
@pytest.mark.parametrize('viewer', VIEWERS)
async def test_references_by_id(client, login_token_factory, read_policy, viewer):
    result = await result_of(
        client, login_token_factory, read_policy, viewer, 'references',
        f"query ($ids: [ID!]) {{ references(ids: $ids) {{ status result {{ {REFERENCE_FIELDS} }} errors {{ name message }} }} }}",
        {'ids': [read_policy[name] for name in REFERENCES]}
    )
    references = {int(reference['id']): reference for reference in result}
    assert set(references) == {read_policy[name] for name in REFERENCES}
    for name in REFERENCES:
        assert_reference(read_policy, viewer, name, references[read_policy[name]])


@pytest.mark.asyncio(loop_scope="session")
@pytest.mark.parametrize('viewer', VIEWERS)
async def test_search(client, login_token_factory, read_policy, viewer):
    result = await result_of(
        client, login_token_factory, read_policy, viewer, 'referencesSearch',
        f"query {{ referencesSearch(description: \"Readpolicy\") {{ status result {{ {REFERENCE_FIELDS} }} errors {{ name message }} }} }}"
    )
    found = {int(reference['id']): reference for reference in result}
    expected = [name for name in REFERENCES if read_policy.readable(viewer, name)]
    assert set(found) == {read_policy[name] for name in expected}
    for name in expected:
        assert_reference(read_policy, viewer, name, found[read_policy[name]])


@pytest.mark.asyncio(loop_scope="session")
@pytest.mark.parametrize('viewer', VIEWERS)
async def test_references_cited_by_a_study(client, login_token_factory, read_policy, viewer):
    result = await result_of(
        client, login_token_factory, read_policy, viewer, 'programsStudy',
        f"query ($id: ID!) {{ programsStudy(id: $id) {{ status result {{ references {{ {REFERENCE_FIELDS} }} }} errors {{ name message }} }} }}",
        {'id': read_policy['study_public']}
    )
    references = {int(reference['id']): reference for reference in result['references']}
    assert set(references) == {read_policy[name] for name in STUDY_REFERENCES['study_public']}
    for name in STUDY_REFERENCES['study_public']:
        assert_reference(read_policy, viewer, name, references[read_policy[name]])


@pytest.mark.asyncio(loop_scope="session")
@pytest.mark.parametrize('viewer', VIEWERS)
async def test_file_download(client, login_token_factory, read_policy, viewer):
    for name, (file_id, content) in read_policy.files.items():
        state = await payload_of(
            client, login_token_factory, read_policy, viewer, 'referencesFileDownloadState',
            "query ($fileId: ID!) { referencesFileDownloadState(fileId: $fileId) { status result { status } errors { name message } } }",
            {'fileId': file_id}
        )
        download = await payload_of(
            client, login_token_factory, read_policy, viewer, 'referencesFileDownload',
            "query ($fileId: ID!) { referencesFileDownload(fileId: $fileId) { status result { url expiresAt } errors { name message } } }",
            {'fileId': file_id}
        )
        if read_policy.readable(viewer, name):
            assert state['status'] == GQLStatus.SUCCESS.name, state['errors']
            assert state['result']['status'] == 'AVAILABLE'
            assert download['status'] == GQLStatus.SUCCESS.name, download['errors']
            response = await client.get(download['result']['url'])
            assert response.status_code == 200
            assert response.content == content
        else:
            for refused in (state, download):
                assert refused['status'] != GQLStatus.SUCCESS.name, f"{viewer} should not get {name}"
                assert refused['result'] is None
                assert [error['name'] for error in refused['errors']] == ['UnauthorisedOperationError']


@pytest.mark.asyncio(loop_scope="session")
@pytest.mark.parametrize('viewer', ('admin', 'anonymous'))
async def test_unknown_file_is_not_found(client, login_token_factory, read_policy, viewer):
    for operation in ('referencesFileDownloadState', 'referencesFileDownload'):
        payload = await payload_of(
            client, login_token_factory, read_policy, viewer, operation,
            f"query ($fileId: ID!) {{ {operation}(fileId: $fileId) {{ status errors {{ name message }} }} }}",
            {'fileId': 'not-a-stored-file'}
        )
        assert payload['status'] != GQLStatus.SUCCESS.name
        assert payload['errors']


@pytest.mark.asyncio(loop_scope="session")
async def test_recent_files_need_an_account(client, login_token_factory, read_policy):
    payload = await payload_of(
        client, login_token_factory, read_policy, 'anonymous', 'referencesRecentFiles',
        "query { referencesRecentFiles { status result { id } errors { name message } } }"
    )
    assert payload['status'] != GQLStatus.SUCCESS.name
    assert payload['result'] is None
