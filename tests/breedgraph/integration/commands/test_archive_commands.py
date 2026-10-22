"""
Asking for an archived file to be retrieved needs read access to its reference (docs/read-access.md §4): a file the
user cannot read is not found, as one that does not exist, and is not asked of the archive.
"""
import uuid

import pytest

from breedgraph.custom_exceptions import NoResultFoundError
from breedgraph.domain.commands.archive import RequestFileRestore
from breedgraph.domain.model.archive import ArchiveState

from tests.breedgraph.scenarios.account_builder import AccountBuilder
from tests.breedgraph.scenarios.archived_files import archived_file


async def requestor_ids(archival_service, file_id: str) -> list[int]:
    return [requestor.id async for requestor in archival_service.get_requestors(file_id)]


@pytest.mark.asyncio(loop_scope="session")
async def test_a_reader_has_an_archived_file_retrieved(bus, uow_factory):
    owner = await AccountBuilder(uow_factory=uow_factory).account_with_affiliations()
    file_id = await archived_file(uow_factory, bus.archival_service, owner)

    await bus.handle(RequestFileRestore(agent_id=owner['user_id'], file_id=file_id))
    assert (await bus.archival_service.get(file_id)).archive_state is ArchiveState.RETRIEVAL_PENDING
    assert await requestor_ids(bus.archival_service, file_id) == [owner['user_id']]


@pytest.mark.asyncio(loop_scope="session")
async def test_a_file_the_user_cannot_read_is_not_found(bus, uow_factory):
    owner = await AccountBuilder(uow_factory=uow_factory).account_with_affiliations()
    stranger = await AccountBuilder(uow_factory=uow_factory).account()
    file_id = await archived_file(uow_factory, bus.archival_service, owner)

    for requested in (file_id, uuid.uuid4().hex):
        with pytest.raises(NoResultFoundError, match="not found"):
            await bus.handle(RequestFileRestore(agent_id=stranger, file_id=requested))
    assert (await bus.archival_service.get(file_id)).archive_state is ArchiveState.ARCHIVED
    assert await requestor_ids(bus.archival_service, file_id) == []
