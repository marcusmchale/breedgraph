import logging

from neo4j import Record

from src.breedgraph.adapters.neo4j.cypher import queries
from src.breedgraph.service_layer.tracking import TrackableProtocol
from src.breedgraph.adapters.neo4j.repositories.controlled import Neo4jControlledRepository

from typing import AsyncGenerator, Type

from src.breedgraph.domain.model.references import (
    ReferenceBase,
    ReferenceStoredBase,
    FileReferenceStored,
    ExternalReferenceStored,
    DataFileStored,
    DataExternalStored,
    LegalReferenceStored
)


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
    def record_to_reference(record: Record) -> ReferenceStoredBase:
        if record.get('text') is not None:
            return LegalReferenceStored(**record)
        elif record.get('url') is not None:
            if record.get('data_format') is not None:
                return DataExternalStored(**record)
            else:
                return ExternalReferenceStored(**record)
        elif record.get('data_format') is not None:
            return DataFileStored(**record)
        else:
            return FileReferenceStored(**record)

    async def _get_controlled(
            self,
            reference_id: int = None
    ) -> ReferenceStoredBase|None:

        if reference_id is None:
            raise TypeError(f"reference_id is required")

        result = await self.tx.run(
            queries['references']['get_reference'],
            reference_id=reference_id
        )
        record = await result.single()
        if record:
            return self.record_to_reference(record.get('reference'))
        else:
            return None

    async def _get_all_controlled(self) -> AsyncGenerator[ReferenceStoredBase, None]:
        result = await self.tx.run(queries['references']['get_references'])
        async for record in result:
            yield self.record_to_reference(record.get('reference'))

    async def _remove_controlled(self, reference: ReferenceStoredBase):
        await self.tx.run(queries['references']['remove_reference'], reference_id=reference.id)

    async def _update_controlled(self, aggregate: ReferenceStoredBase | TrackableProtocol):
        if aggregate.changed:
            await self._update_reference(aggregate)

    async def _update_reference(self, reference: ReferenceStoredBase):
        params = reference.model_dump()
        reference_id = params.pop('id')
        await self.tx.run(queries['references']['set_reference'], reference_id=reference_id, params=params)
