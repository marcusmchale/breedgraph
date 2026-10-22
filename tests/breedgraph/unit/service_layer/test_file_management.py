"""
Saving uploaded files (service_layer/infrastructure/file_management.py): at most MAX_CONCURRENT_UPLOADS at once. An
upload asked for while they are all taken is refused then, and one accepted waits its turn rather than failing in the
background. Fixture-free, so it can run without the database:
python -m pytest --noconftest -p no:cacheprovider tests/breedgraph/unit/service_layer/test_file_management.py
"""
import asyncio
import io

import pytest
from fastapi import UploadFile

from breedgraph.custom_exceptions import TooManyUploadsError
from breedgraph.domain.model.submissions import SubmissionStatus
from breedgraph.service_layer.infrastructure import file_management
from breedgraph.service_layer.infrastructure.file_management import FileManagementService


class RecordingStateStore:
    def __init__(self):
        self.statuses = {}

    async def set_status(self, uuid, status):
        self.statuses[uuid] = status

    async def set_file_progress(self, uuid, progress):
        pass

    async def set_errors(self, uuid, errors):
        pass


@pytest.fixture
def service(tmp_path, monkeypatch):
    monkeypatch.setattr(file_management, 'FILE_STORAGE_PATH', str(tmp_path))
    return FileManagementService(state_store=RecordingStateStore())


async def take_every_place(service: FileManagementService):
    for _ in range(file_management.MAX_CONCURRENT_UPLOADS):
        await service.upload_semaphore.acquire()


@pytest.mark.asyncio
async def test_an_upload_is_refused_while_every_place_is_taken(service):
    service.require_capacity()
    await take_every_place(service)
    with pytest.raises(TooManyUploadsError, match='try again'):
        service.require_capacity()


@pytest.mark.asyncio
async def test_an_accepted_upload_waits_its_turn(service, tmp_path):
    await take_every_place(service)
    upload = UploadFile(io.BytesIO(b'unit,height\n'), size=12, filename='heights.csv')
    saving = asyncio.create_task(service.save_file('key', upload))
    await asyncio.sleep(0.05)
    assert not saving.done()
    # a place freed goes to it, so another upload is still refused
    service.upload_semaphore.release()
    with pytest.raises(TooManyUploadsError):
        service.require_capacity()

    await asyncio.wait_for(saving, 5)
    assert service.state_store.statuses['key'] is SubmissionStatus.COMPLETED
    assert (tmp_path / 'key').read_bytes() == b'unit,height\n'
