"""
A file whose local copy has expired, leaving it on the archive server, for tests of asking for archived files and of
being told they are back (integration/commands/test_archive_commands.py, integration/events/test_archive_events.py)
"""
import hashlib
import uuid
from datetime import datetime

from breedgraph.domain.model.archive import FileArchivalRecord, ArchiveState, LocalState
from breedgraph.domain.model.controls import ReadRelease
from breedgraph.domain.model.references import FileReferenceInput

CONTENT = b"unit,height\ntree,310\n"


async def archived_file(uow_factory, archival_service, owner: dict) -> str:
    """The file id of a private file reference of the owner's team, whose file is archived and gone from the web server"""
    file_id = uuid.uuid4().hex
    async with uow_factory.get_uow(user_id=owner['user_id'], write_team=owner['team_id'], release=ReadRelease.PRIVATE) as uow:
        await uow.repositories.references.create(FileReferenceInput(
            description='Archived data', filename='archived.csv', content_type='text/csv', file_id=file_id
        ))
        await uow.commit()
    await archival_service.create(FileArchivalRecord(
        file_id=file_id,
        file_size=len(CONTENT),
        file_hash=hashlib.sha256(CONTENT).hexdigest(),
        last_accessed=datetime.now(),
        archive_state=ArchiveState.ARCHIVED,
        local_state=LocalState.EXPIRED
    ))
    return file_id
