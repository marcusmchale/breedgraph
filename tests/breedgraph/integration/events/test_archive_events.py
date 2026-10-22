"""
Retrieving an archived file tells those who asked for it, by email: that it can be downloaded from the site, if they
can still read its reference, or that the retrieval failed. A retrieval meets the requests, so they are cleared, while
a failed one keeps them. The email links to the site rather than to the file, whose download checks the licences of the
data citing it (docs/licences.md §5).
"""
from pathlib import Path

import pytest

from breedgraph.config import get_vue_url, FILE_STORAGE_PATH
from breedgraph.domain.events.archive import RetrievalSucceeded, RetrievalFailed
from breedgraph.domain.model.archive import ArchiveState, LocalState
from breedgraph.service_layer.handlers.events.archive import retrieval_succeeded, retrieval_failed

from tests.breedgraph.scenarios.account_builder import AccountBuilder
from tests.breedgraph.scenarios.archived_files import archived_file, CONTENT


class RecordingNotifications:
    def __init__(self):
        self.sent = []

    async def send(self, recipients, message):
        self.sent.append((recipients, message))


def recipient_ids(notifications: RecordingNotifications) -> list[list[int]]:
    return [[recipient.id for recipient in recipients] for recipients, _ in notifications.sent]


@pytest.mark.asyncio(loop_scope="session")
async def test_a_retrieval_emails_those_who_asked_and_can_read_the_file(bus, uow_factory):
    archival_service = bus.archival_service
    owner = await AccountBuilder(uow_factory=uow_factory).account_with_affiliations()
    stranger = await AccountBuilder(uow_factory=uow_factory).account()
    file_id = await archived_file(uow_factory, archival_service, owner)
    for user_id in (owner['user_id'], stranger):
        await archival_service.add_requestor(file_id=file_id, user_id=user_id)
    requestors = [requestor.id async for requestor in archival_service.get_requestors(file_id)]
    assert sorted(requestors) == sorted([owner['user_id'], stranger])

    notifications = RecordingNotifications()
    await retrieval_succeeded(
        RetrievalSucceeded(file_id=file_id), archival_service=archival_service, uow_factory=uow_factory,
        notifications=notifications
    )
    # the stranger cannot read the private reference, so is not told of it
    assert recipient_ids(notifications) == [[owner['user_id']]]
    message = notifications.sent[0][1].message
    body = message.get_content()
    assert message['Subject'].endswith('file retrieved from archive')
    assert 'archived.csv' in body and get_vue_url() in body
    assert 'token=' not in body

    # the requests are met
    assert [requestor async for requestor in archival_service.get_requestors(file_id)] == []
    assert (await archival_service.get(file_id)).retrieval_requested_at is None


@pytest.mark.asyncio(loop_scope="session")
async def test_a_failed_retrieval_tells_those_who_asked_and_keeps_their_requests(bus, uow_factory):
    archival_service = bus.archival_service
    owner = await AccountBuilder(uow_factory=uow_factory).account_with_affiliations()
    file_id = await archived_file(uow_factory, archival_service, owner)
    await archival_service.add_requestor(file_id=file_id, user_id=owner['user_id'])

    notifications = RecordingNotifications()
    await retrieval_failed(
        RetrievalFailed(file_id=file_id, error_message='Failed to retrieve this file after 5 attempts'),
        archival_service=archival_service, notifications=notifications
    )
    assert recipient_ids(notifications) == [[owner['user_id']]]
    message = notifications.sent[0][1].message
    assert message['Subject'].endswith('file retrieval from archive failed')
    assert 'after 5 attempts' in message.get_content()
    # so they hear if it is retrieved after all
    assert [requestor.id async for requestor in archival_service.get_requestors(file_id)] == [owner['user_id']]


@pytest.mark.asyncio(loop_scope="session")
async def test_a_retrieved_file_is_kept_as_long_as_after_a_download(bus, uow_factory, event_queue):
    archival_service = bus.archival_service
    owner = await AccountBuilder(uow_factory=uow_factory).account_with_affiliations()
    file_id = await archived_file(uow_factory, archival_service, owner)
    last_accessed = (await archival_service.get(file_id)).last_accessed
    # back from the archive, as the archive worker writes it
    path = Path(FILE_STORAGE_PATH, file_id)
    path.write_bytes(CONTENT)
    try:
        await archival_service.update_archive_state(file_id, archive_state=ArchiveState.RETRIEVED)
        await event_queue.join()
        record = await archival_service.get(file_id)
        assert (record.archive_state, record.local_state) == (ArchiveState.ARCHIVED, LocalState.LOCAL)
        # its time on the web server counts from its retrieval, not from its last use before
        assert record.last_accessed > last_accessed
    finally:
        path.unlink(missing_ok=True)
