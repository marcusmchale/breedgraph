"""
referencesFileDownloadState says whether a file can be downloaded and, for an archived one, how far its retrieval has
got (FileDownloadState.progress), which breedview's download button shows
"""
import pytest

from breedgraph.domain.commands.archive import RequestFileRestore

from tests.breedgraph.e2e.utils import post_as, get_verified_payload
from tests.breedgraph.scenarios.account_builder import AccountBuilder
from tests.breedgraph.scenarios.archived_files import archived_file

STATE = """
    query ($fileId: ID!) {
        referencesFileDownloadState(fileId: $fileId) {
            status result { status progress { startedAt progress } } errors { message }
        }
    }
"""


async def download_state(client, login_token_factory, user_id: int, file_id: str) -> dict:
    response = await post_as(client, login_token_factory, user_id, STATE, {'fileId': file_id})
    payload = get_verified_payload(response, "referencesFileDownloadState")
    assert payload['status'] == 'SUCCESS', payload['errors']
    return payload['result']


@pytest.mark.asyncio(loop_scope="session")
async def test_an_archived_file_shows_how_far_its_retrieval_has_got(client, bus, uow_factory, login_token_factory):
    owner = await AccountBuilder(uow_factory=uow_factory).account_with_affiliations()
    file_id = await archived_file(uow_factory, bus.archival_service, owner)
    assert await download_state(client, login_token_factory, owner['user_id'], file_id) == {
        'status': 'ARCHIVED', 'progress': {'startedAt': None, 'progress': 0}
    }

    await bus.handle(RequestFileRestore(agent_id=owner['user_id'], file_id=file_id))
    state = await download_state(client, login_token_factory, owner['user_id'], file_id)
    assert state['status'] == 'RETRIEVING'
    assert state['progress']['progress'] == 0 and state['progress']['startedAt'] is not None
