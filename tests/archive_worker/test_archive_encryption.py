"""
The archive worker's client against the BreedGraph archive endpoints, with an in-memory archival service:
files reach the archive server encrypted, and come back decrypted. Needs age on the PATH, but no database.
"""
import asyncio
import hashlib
import shutil
import subprocess
from pathlib import Path
from types import SimpleNamespace

import httpx
import pytest
import pytest_asyncio
from fastapi import FastAPI

from archive_worker.adapters.http.client import ArchiveAPIClient
from archive_worker.service_layer.handlers import handle_archival, handle_retrieval

from breedgraph import config
from breedgraph.custom_exceptions import NoResultFoundError
from breedgraph.domain.model.archive import FileArchivalRecord, ArchiveState, LocalState
from breedgraph.entrypoints.fastapi.archive import router
from breedgraph.service_layer.infrastructure.archival_service import AbstractFileArchivalService

pytestmark = pytest.mark.skipif(
    shutil.which('age') is None or shutil.which('age-keygen') is None,
    reason="needs age (https://age-encryption.org)"
)

TOKEN = "test-archive-token"
FILE_ID = "file-1"
CONTENT = b"Plant height, leaf area and yield. " * 60_000  # about 2 MB, so more than one chunk
RECORD = {"file_id": FILE_ID, "file_size": len(CONTENT), "file_hash": hashlib.sha256(CONTENT).hexdigest()}


class InMemoryArchivalService(AbstractFileArchivalService):
    def __init__(self, file_storage_path: Path):
        self.driver = None
        self.queue = asyncio.Queue()
        self.file_storage_path = file_storage_path
        self.records: dict[str, FileArchivalRecord] = {}

    async def create(self, record: FileArchivalRecord) -> FileArchivalRecord:
        self.records[record.file_id] = record
        return record

    async def get(self, file_id: str) -> FileArchivalRecord:
        return self.records[file_id]

    async def mark_accessed(self, file_id: str):
        pass

    async def set_archive_hash(self, file_id: str, archive_hash: str) -> None:
        self.records[file_id].archive_hash = archive_hash

    async def _set_retrieved(self, file_id: str, file_hash: str) -> FileArchivalRecord:
        record = self.records[file_id]
        if record.file_hash != file_hash:
            raise NoResultFoundError
        record.archive_state = ArchiveState.ARCHIVED
        record.local_state = LocalState.LOCAL
        return record

    async def _clear_attempts(self, file_id: str) -> None:
        self.records[file_id].attempts = 0

    async def delete_record(self, file_id: str):
        del self.records[file_id]

    async def _set_state_values(self, file_id, archive_state=None, local_state=None) -> FileArchivalRecord:
        record = self.records[file_id]
        if archive_state:
            record.archive_state = archive_state
        if local_state:
            record.local_state = local_state
        return record

    async def add_requestor(self, file_id: str, user_id: int):
        pass

    async def get_requestors(self, file_id: str):
        for requestor in ():
            yield requestor

    async def clear_requestors(self, file_id: str):
        pass

    async def get_expired_local(self):
        for record in ():
            yield record


@pytest.fixture
def key_file(tmp_path) -> Path:
    path = tmp_path / "encryption_key.txt"
    subprocess.run(['age-keygen', '-o', str(path)], check=True, capture_output=True)
    return path


@pytest.fixture
def recipient(key_file) -> str:
    return subprocess.run(
        ['age-keygen', '-y', str(key_file)], check=True, capture_output=True, text=True
    ).stdout.strip()


@pytest.fixture
def storage(tmp_path) -> Path:
    path = tmp_path / "file_store"
    path.mkdir()
    (path / FILE_ID).write_bytes(CONTENT)
    return path


@pytest.fixture
def archive(tmp_path) -> Path:
    path = tmp_path / "archive"
    path.mkdir()
    return path


@pytest.fixture
def settings(monkeypatch, storage, key_file, recipient):
    monkeypatch.setattr(config, 'ARCHIVE_AUTH_TOKEN', TOKEN)
    monkeypatch.setattr(config, 'FILE_STORAGE_PATH', str(storage))
    monkeypatch.setattr(config, 'ENCRYPTION_RECIPIENT', recipient)
    monkeypatch.setattr(config, 'ENCRYPTION_IDENTITY_PATH', str(key_file))
    monkeypatch.setattr(config, 'ENVIRONMENT', config.Environment.PRODUCTION)


@pytest.fixture
def archival_service(storage) -> InMemoryArchivalService:
    service = InMemoryArchivalService(storage)
    service.records[FILE_ID] = FileArchivalRecord(
        file_id=FILE_ID,
        file_size=len(CONTENT),
        file_hash=RECORD['file_hash'],
        archive_state=ArchiveState.ARCHIVING
    )
    return service


@pytest_asyncio.fixture
async def client(settings, archival_service):
    app = FastAPI()
    app.include_router(router)
    app.bus = SimpleNamespace(archival_service=archival_service)
    api_client = ArchiveAPIClient(base_url="http://breedgraph", auth_token=TOKEN)
    await api_client.client.aclose()
    api_client.client = httpx.AsyncClient(transport=httpx.ASGITransport(app=app), timeout=30)
    yield api_client
    await api_client.close()


def expire_local_copy(archival_service: InMemoryArchivalService, storage: Path):
    """As the retention job does once a file is archived, then ask for it back"""
    (storage / FILE_ID).unlink()
    record = archival_service.records[FILE_ID]
    record.local_state = LocalState.EXPIRED
    record.archive_state = ArchiveState.RETRIEVING


@pytest.mark.asyncio
async def test_archived_copy_is_encrypted(client, archival_service, archive):
    await handle_archival(client, archive, RECORD)

    stored = (archive / FILE_ID).read_bytes()
    assert stored.startswith(b"age-encryption.org/v1\n")
    assert b"Plant height" not in stored
    record = archival_service.records[FILE_ID]
    assert record.archive_state is ArchiveState.ARCHIVED
    assert record.archive_hash == hashlib.sha256(stored).hexdigest()
    assert [path.name for path in archive.iterdir()] == [FILE_ID]


@pytest.mark.asyncio
async def test_retrieved_copy_is_decrypted(client, archival_service, archive, storage):
    await handle_archival(client, archive, RECORD)
    expire_local_copy(archival_service, storage)

    await handle_retrieval(client, archive, RECORD)

    assert (storage / FILE_ID).read_bytes() == CONTENT
    assert [path.name for path in storage.iterdir()] == [FILE_ID]
    record = archival_service.records[FILE_ID]
    assert record.archive_state is ArchiveState.ARCHIVED
    assert record.local_state is LocalState.LOCAL


@pytest.mark.asyncio
async def test_altered_archived_copy_is_not_retrieved(client, archival_service, archive, storage):
    await handle_archival(client, archive, RECORD)
    stored = bytearray((archive / FILE_ID).read_bytes())
    stored[-100] ^= 1
    (archive / FILE_ID).write_bytes(stored)
    expire_local_copy(archival_service, storage)

    with pytest.raises(httpx.HTTPStatusError):
        await handle_retrieval(client, archive, RECORD)

    assert list(storage.iterdir()) == []
    assert archival_service.records[FILE_ID].archive_state is ArchiveState.RETRIEVAL_PENDING


@pytest.mark.asyncio
async def test_archived_copy_must_match_what_was_sent(client, archival_service, archive):
    await client.download_file(FILE_ID, archive)

    with pytest.raises(httpx.HTTPStatusError) as error:
        await client.update_state(FILE_ID, {
            "archive_state": ArchiveState.ARCHIVED.value,
            "archive_hash": hashlib.sha256(b"something else").hexdigest()
        })

    assert error.value.response.status_code == 409
    assert archival_service.records[FILE_ID].archive_state is ArchiveState.ARCHIVAL_PENDING


@pytest.mark.asyncio
async def test_unencrypted_in_development_without_a_key(client, archival_service, archive, storage, monkeypatch):
    monkeypatch.setattr(config, 'ENCRYPTION_RECIPIENT', None)
    monkeypatch.setattr(config, 'ENCRYPTION_IDENTITY_PATH', None)
    monkeypatch.setattr(config, 'ENVIRONMENT', config.Environment.DEVELOPMENT)

    await handle_archival(client, archive, RECORD)
    assert (archive / FILE_ID).read_bytes() == CONTENT
    assert archival_service.records[FILE_ID].archive_state is ArchiveState.ARCHIVED

    expire_local_copy(archival_service, storage)
    await handle_retrieval(client, archive, RECORD)
    assert (storage / FILE_ID).read_bytes() == CONTENT
    assert archival_service.records[FILE_ID].local_state is LocalState.LOCAL


@pytest.mark.asyncio
async def test_no_transfers_without_a_key_outside_development(client, archive, monkeypatch):
    monkeypatch.setattr(config, 'ENCRYPTION_RECIPIENT', None)

    with pytest.raises(httpx.HTTPStatusError) as error:
        await client.download_file(FILE_ID, archive)
    assert error.value.response.status_code == 503
    assert list(archive.iterdir()) == []

    (archive / FILE_ID).write_bytes(CONTENT)
    with pytest.raises(httpx.HTTPStatusError) as error:
        await client.upload_file(FILE_ID, archive)
    assert error.value.response.status_code == 503
