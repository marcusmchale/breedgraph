from neo4j import Record
from datetime import datetime
from pathlib import Path

from breedgraph.service_layer.infrastructure.archival_service import AbstractFileArchivalService
from breedgraph.domain.model.archive import FileArchivalRecord, ArchiveState, LocalState, ArchiveRequestor
from breedgraph.adapters.neo4j.cypher import queries

from breedgraph.config.files import LOCAL_STORAGE_DURATION, LOCAL_SIZE_LIMIT

from typing import AsyncGenerator


import logging
logger = logging.getLogger(__name__)


class Neo4jFileArchivalService(AbstractFileArchivalService):
    """Manages file archival metadata in Neo4j.

    Handles persistence of FileArchivalRecord entities which track the state
    of large files being archived/retrieved from a separate archive server.
    """

    def record_to_archival_record(self, record: Record | dict) -> FileArchivalRecord:
        """Convert Neo4j record to FileArchivalRecord"""
        if isinstance(record, Record):
            record = record.data()

        if 'record' in record:
            record = record.get('record', {})

        # Convert string states back to enums
        record['archive_state'] = ArchiveState(record['archive_state'])
        record['local_state'] = LocalState(record['local_state'])

        # Convert timestamps
        if record.get('last_attempt_at'):
            record['last_attempt_at'] = datetime.fromisoformat(record['last_attempt_at'])
        if record.get('last_accessed'):
            record['last_accessed'] = datetime.fromisoformat(record['last_accessed'])

        file_size: int = record['file_size']
        file_path = Path(self.file_storage_path, record['file_id'])
        record['local_completion'] = int(100 * file_path.stat().st_size / file_size)
        return FileArchivalRecord(**record)

    @staticmethod
    def archival_record_to_props(record: FileArchivalRecord) -> dict:
        """Convert FileArchivalRecord to Neo4j properties"""
        props = {
            'file_id': record.file_id,
            'file_size': record.file_size,
            'file_hash': record.file_hash,
            'last_accessed': record.last_accessed.isoformat(),
            'archive_state': record.archive_state.value,
            'local_state': record.local_state.value,
            'attempts': record.attempts,
            'last_attempt_at': record.last_attempt_at.isoformat() if record.last_attempt_at else None,
        }
        return props

    async def create(self, record: FileArchivalRecord) -> FileArchivalRecord:
        """Create a new archival record"""
        logger.debug(f"Creating archival record for file {record.file_id}")
        async with self.driver.session() as session:
            result = await session.run(
                queries['archive']['create_record'],
                file_id = record.file_id,
                record_data=self.archival_record_to_props(record)
            )
            returned_record = await result.single(strict=True)
        return self.record_to_archival_record(returned_record)

    async def get(self, file_id: str) -> FileArchivalRecord:
        async with self.driver.session() as session:
            result = await session.run(
                queries['archive']['get_record'],
                file_id = file_id
            )
            return await result.single(strict=True)

    async def _set_state_values(
            self,
            file_id: str,
            archive_state: ArchiveState | None = None,
            local_state: LocalState | None = None
    ) -> FileArchivalRecord:
        if not any([archive_state, local_state]):
            raise ValueError("State values are required to set state values")

        update_data = {}

        if archive_state:
            update_data["archive_state"] = archive_state.value
        if local_state:
            update_data["local_state"] = local_state.value

        async with self.driver.session() as session:
            result = await session.run(
                queries['archive']['update_record'],
                file_id=file_id,
                updates=update_data
            )
            record = await result.single(strict=True)
            return self.record_to_archival_record(record)

    async def _set_retrieved(self, file_id, file_hash: str) -> FileArchivalRecord | None:
        async with self.driver.session() as session:
            result = await session.run(
                queries['set_retrieved'],
                file_id=file_id,
                file_hash=file_hash
            )
            record = result.single(strict=True)
            return record.value()

    async def _clear_attempts(self, file_id: str) -> None:
        async with self.driver.session() as session:
            await session.run(
                queries['clear_attempts'],
                file_id=file_id
            )

    async def delete_record(self, file_id: str) -> None:
        async with self.driver.session() as session:
            await session.run(
                queries['archive']['delete_record'],
                file_id=file_id
            )

    async def _collect_record(self, state: ArchiveState) -> FileArchivalRecord|None:
        async with self.driver.session() as session:
            async with await session.begin_transaction() as tx:
                result = await tx.run(
                    queries['archive']['get_records_by_states'],
                    archive_states=[state.value]
                )
                archival_record = await result.single(strict=False)
                if archival_record is None:
                    return None

                archival_record.archive_state = self.COLLECTION_TRANSITIONS[state]
                archival_record.attempts += 1
                archival_record.last_attempt_at = datetime.now()
                props = self.archival_record_to_props(archival_record)
                props.pop('file_id')
                result = await tx.run(
                    queries['archive']['update_record'],
                    file_id=archival_record.file_id,
                    updates=props
                )
                record = await result.single(strict=True)
                return self.record_to_archival_record(record)

    async def mark_accessed(self, file_id: str):
        async with self.driver.session() as session:
            await session.run(queries['archive']['mark_accessed'], file_id=file_id)

    async def add_requestor(self, file_id: str, user_id: int) -> None:
        async with self.driver.session() as session:
            await session.run(
                queries['archive']['add_requestor'],
                file_id=file_id,
                user_id=user_id
            )
        # marking as accessed directly in the add_requestor query
        # instead of needing a separate call
        # await self.mark_accessed(file_id)

    async def get_requestors(self, file_id: str) -> AsyncGenerator[ArchiveRequestor, None]:
        async with self.driver.session() as session:
            result = await session.run(queries['archive']['get_requestors'], file_id=file_id)
            async for record in result:
                requestor = record.get("requestor")
                yield ArchiveRequestor(
                    id = requestor.get('id'),
                    name = requestor.get('fullname'),
                    email = requestor.get('email')
                )

    async def clear_requestors(self, file_id: str) -> None:
        async with self.driver.session() as session:
            await session.run(queries['archive']['clear_requestors'], file_id=file_id)

    async def get_expired_local(self) -> AsyncGenerator[FileArchivalRecord, None]:
        async with self.driver.session() as session:
            async for record in await session.run(
                    queries['archive']['get_expired_local_records'],
                    size_limit = LOCAL_SIZE_LIMIT,
                    age_limit= LOCAL_STORAGE_DURATION
            ):
                yield self.record_to_archival_record(record)
