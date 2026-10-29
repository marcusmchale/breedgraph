import json

from neo4j import Record

from breedgraph.adapters.neo4j.cypher import queries
from breedgraph.custom_exceptions import UnauthorisedOperationError
from breedgraph.domain.model.contributions import contributions_from
from breedgraph.service_layer.tracking import TrackableProtocol
from breedgraph.adapters.neo4j.repositories.controlled import Neo4jControlledRepository
from breedgraph.service_layer.repositories.controlled import ControlledQueryResult, DiscoveryMatch

from typing import AsyncGenerator, List

from breedgraph.domain.model.references import (
    ReferenceType,
    ReferenceBase,
    ReferenceStoredBase,
    FileReferenceStored,
    ExternalReferenceStored,
    DataFileStored,
    ExternalDataStored,
    LegalReferenceStored,
    DataFormat,
    TextFormat,
    text_hash
)

import logging
logger = logging.getLogger(__name__)


REFERENCE_TYPE_MAP: dict[
    ReferenceType,
    type[ReferenceStoredBase]
] = {
    ReferenceType.LEGAL: LegalReferenceStored,
    ReferenceType.EXTERNAL: ExternalReferenceStored,
    ReferenceType.FILE: FileReferenceStored,
    ReferenceType.EXTERNAL_DATA: ExternalDataStored,
    ReferenceType.DATA_FILE: DataFileStored
}

class Neo4jReferencesRepository(Neo4jControlledRepository[ReferenceBase, ReferenceStoredBase]):

    async def _create_controlled(
            self,
            reference: ReferenceBase,
    ) -> ReferenceStoredBase:
        params = reference.model_dump()
        contributions = params.pop('contributions', None)
        result = await self.tx.run(queries['references']['create_reference'], params=params)
        record = await result.single()
        stored = self.record_to_reference(record.get('reference'))
        if contributions:
            await self._set_contributions(stored.id, contributions)
            stored.contributions = contributions_from(contributions)
        return stored

    async def seed(self, reference: ReferenceBase, seed_key: str) -> ReferenceStoredBase:
        """
        Create a reference without controls, so it is fixed: everyone can read it and no one can change it
        (docs/read-access.md, rule 11). It is keyed, for seeding again to find it: the standard licences
        (service_layer/application/licence_seed.py).
        """
        if self.user_id is None:
            raise UnauthorisedOperationError("Seeding references requires a user_id")
        stored = await self._create_controlled(reference)
        await self.tx.run(queries['references']['set_seed_key'], reference_id=stored.id, seed_key=seed_key)
        await self.controls.record_writes(stored)
        return stored

    async def get_seeded_id(self, seed_key: str) -> int | None:
        """The id of the reference seeded with this key"""
        result = await self.tx.run(queries['references']['get_reference_id_by_seed_key'], seed_key=seed_key)
        record = await result.single()
        return record['id'] if record else None

    async def _set_contributions(self, reference_id: int, contributions: list[dict]) -> None:
        await self.tx.run(queries['references']['set_contributions'], reference_id=reference_id, contributions=contributions)

    @staticmethod
    def record_to_reference(record: Record|dict) -> ReferenceStoredBase:
        if isinstance(record, Record):
            record = record.data()
        if 'reference' in record:
            record = record.get('reference')
        if not record:
            raise ValueError("No reference record provided")


        reference_type = ReferenceType(record['type'])
        if 'format' in record:
            record['format'] = DataFormat(record['format'])
        if 'text_format' in record:
            record['text_format'] = TextFormat(record['text_format'])
        if 'schema' in record:
            record['schema'] = json.loads(record['schema'])
        # the retention job's mark (remove_unused_files), and the key of a seeded reference, not part of the reference
        record.pop('unused_since', None)
        record.pop('seed_key', None)
        # legal text written before content hashes were kept was typed, so its hash is that of the text
        if reference_type == ReferenceType.LEGAL and record.get('content_hash') is None and record.get('text') is not None:
            record['content_hash'] = text_hash(record['text'])

        if not reference_type in REFERENCE_TYPE_MAP:
            raise ValueError("Reference type not found")
        else:
            reference_class = REFERENCE_TYPE_MAP.get(reference_type)
            # only files, data files and external data credit Persons; the reads give the others none
            contributions = record.pop('contributions', None)
            if 'contributions' in reference_class.__dataclass_fields__:
                record['contributions'] = contributions_from(contributions)
            return reference_class(**record)


    async def _get_controlled(
            self,
            reference_id: int|None = None,
            file_id: str|None = None,
            description: str | None = None
    ) -> ControlledQueryResult[ReferenceStoredBase]|None:
        if reference_id:
            result = await self.tx.run(
                queries['references']['get_reference'],
                reference_id=reference_id
            )
            record = await result.single(strict=True)
            return ControlledQueryResult(self.record_to_reference(record.get('reference')))
        else:
            try:
                return await anext(
                    self._get_all_controlled(
                        file_ids=[file_id] if file_id else None,
                        description=description
                    )
                )
            except StopAsyncIteration:
                return None

    async def _get_all_controlled(
            self,
            reference_ids: list[int]|None = None,
            file_ids: list[str]|None = None,
            description: str|None = None,
            reference_types: list[ReferenceType]|None = None
    ) -> AsyncGenerator[ControlledQueryResult[ReferenceStoredBase], None]:
        match_field = None
        if reference_ids is not None:
            result = await self.tx.run(queries['references']['get_references_by_ids'], reference_ids=reference_ids)
        elif file_ids is not None:
            result = await self.tx.run(queries['references']['get_references_by_file_ids'], file_ids=file_ids)
            match_field = "file_id"
        elif description is not None:
            if reference_types is not None:
                result = await self.tx.run(
                    queries['references']['get_references_by_description_and_types'],
                    description=description,
                    types=reference_types
                )
                match_field = "description"
            else:
                result = await self.tx.run(
                    queries['references']['get_references_by_description'],
                    description=description
                )
                match_field = "description"
        else:
            result = await self.tx.run(queries['references']['get_references'])

        async for record in result:
            reference = self.record_to_reference(record)
            if hasattr(reference, 'type') and reference_types:
                if not reference.type in reference_types:
                    continue

            if match_field is None:
                yield ControlledQueryResult(reference)
            else:
                matches = (DiscoveryMatch(label=ReferenceBase.label, model_id=reference.id, key=match_field),)
                yield ControlledQueryResult(reference, matches=matches)


    async def _remove_controlled(self, reference: ReferenceStoredBase):
        await self.tx.run(queries['references']['remove_reference'], reference_id=reference.id)

    async def remove_unused_files(self, days: int) -> List[str]:
        """
        For the retention job, whatever the user's access, as remove_expired does for invitations: mark when each file
        reference was first found unused (nothing cites it), and remove those unused, and not written, for more than
        days. Each run marks, so a reference unlinked today is kept for days from the next run.
        Returns the IDs of their files.
        """
        await self.tx.run(queries['references']['mark_unused_file_references'])
        result = await self.tx.run(queries['references']['remove_unused_file_references'], days=days)
        return [record['file_id'] async for record in result if record['file_id'] is not None]

    async def _update_controlled(self, aggregate: ReferenceStoredBase | TrackableProtocol):
        if aggregate.changed:
            await self._update_reference(aggregate)

    async def _update_reference(self, reference: ReferenceStoredBase):
        params = reference.model_dump()
        reference_id = params.pop('id')
        contributions = params.pop('contributions', None)
        await self.tx.run(queries['references']['set_reference'], reference_id=reference_id, params=params)
        if contributions is not None:
            await self._set_contributions(reference_id, contributions)
