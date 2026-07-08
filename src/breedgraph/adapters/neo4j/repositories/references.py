import json

from neo4j import Record

from breedgraph.adapters.neo4j.cypher import queries
from breedgraph.service_layer.tracking import TrackableProtocol
from breedgraph.adapters.neo4j.repositories.controlled import Neo4jControlledRepository
from breedgraph.service_layer.repositories.controlled import ControlledQueryResult, DiscoveryMatch

from typing import AsyncGenerator, List

from breedgraph.domain.model.references import (
    ReferenceBase,
    ReferenceStoredBase,
    FileReferenceStored,
    ExternalReferenceStored,
    DataFileStored,
    ExternalDataStored,
    LegalReferenceStored,
    DataFormat
)

import logging
logger = logging.getLogger(__name__)


class Neo4jReferencesRepository(Neo4jControlledRepository[ReferenceBase, ReferenceStoredBase]):

    async def _create_controlled(
            self,
            reference: ReferenceBase,
    ) -> ReferenceStoredBase:
        params = reference.model_dump()
        result = await self.tx.run(queries['references']['create_reference'], params=params)
        record = await result.single()
        return self.record_to_reference(record.get('reference'))

    @staticmethod
    def record_to_reference(record: Record|dict) -> ReferenceStoredBase:
        if isinstance(record, Record):
            record = record.data()
        if 'reference' in record:
            record = record.get('reference')

        if 'format' in record:
            record['format'] = DataFormat(record['format'])
        if 'schema' in record:
            record['schema'] = json.loads(record['schema'])

        if record.get('text') is not None:
            return LegalReferenceStored(**record)

        elif record.get('url') is not None:
            if record.get('format') is not None:
                return ExternalDataStored(**record)
            else:
                return ExternalReferenceStored(**record)
        elif record.get('format') is not None:
            return DataFileStored(**record)
        else:
            return FileReferenceStored(**record)

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
            reference_ids: List[int]|None = None,
            file_ids: List[str]|None = None,
            description: str|None = None
    ) -> AsyncGenerator[ControlledQueryResult[ReferenceStoredBase], None]:
        match_field = None
        if reference_ids:
            result = await self.tx.run(queries['references']['get_references_by_ids'], reference_ids=reference_ids)
        elif file_ids:
            result = await self.tx.run(queries['references']['get_references_by_file_ids'], file_ids=file_ids)
            match_field = "file_id"
        elif description:
            result = await self.tx.run(queries['references']['get_references_by_description'], description=description)
            match_field = "description"
        else:
            result = await self.tx.run(queries['references']['get_references'])

        async for record in result:
            reference = self.record_to_reference(record)
            if match_field is None:
                yield ControlledQueryResult(reference)
            else:
                matches = (DiscoveryMatch(label=ReferenceBase.label, model_id=reference.id, key=match_field),)
                yield ControlledQueryResult(reference, matches=matches)


    async def _remove_controlled(self, reference: ReferenceStoredBase):
        await self.tx.run(queries['references']['remove_reference'], reference_id=reference.id)

    async def _update_controlled(self, aggregate: ReferenceStoredBase | TrackableProtocol):
        if aggregate.changed:
            await self._update_reference(aggregate)

    async def _update_reference(self, reference: ReferenceStoredBase):
        params = reference.model_dump()
        reference_id = params.pop('id')
        await self.tx.run(queries['references']['set_reference'], reference_id=reference_id, params=params)
