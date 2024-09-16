import logging

from numpy import datetime_data, datetime64

from src.breedgraph.custom_exceptions import UnauthorisedOperationError

from src.breedgraph.adapters.neo4j.cypher import queries

from src.breedgraph.adapters.repositories.trackable_wrappers import Tracked
from src.breedgraph.adapters.repositories.controlled import Neo4jControlledRepository

from typing import AsyncGenerator, Set, Tuple, List

from src.breedgraph.domain.model.controls import Access, WriteStamp
from src.breedgraph.domain.model.germplasm import (
    GermplasmEntryInput, GermplasmEntryStored, Germplasm,
    GermplasmSourceType
)
from src.breedgraph.domain.model.time_descriptors import PyDT64

logger = logging.getLogger(__name__)


class Neo4jGermplasmRepository(Neo4jControlledRepository):

    async def _create_controlled(self, entry: GermplasmEntryInput) -> Germplasm:
        entry = await self._create_entry(entry)
        return Germplasm(nodes=[entry])

    @staticmethod
    def record_to_entry(record):
        if 'time' in record:
            record['time'] = datetime64(record['time'], (record['time_unit'], record['time_step']))
        return GermplasmEntryStored(**record)

    async def _create_entry(self, entry: GermplasmEntryInput) -> GermplasmEntryStored:
        logger.debug(f"Create germplasm entry: {entry}")
        result = await self.tx.run(queries['germplasm']['create_entry'], **entry.model_dump())
        record = await result.single()
        return self.record_to_entry(record.get('entry'))

    async def _update_entry(self, entry: GermplasmEntryStored):
        logger.debug(f"Set germplasm entry: {entry}")
        result = await self.tx.run(queries['germplasm']['set_entry'], **entry.model_dump())
        record = await result.single()
        return self.record_to_entry(record.get('entry'))

    async def _delete_entries(self, entry_ids: List[int]):
        logger.debug(f"Delete germplasm entries: {entry_ids}")
        await self.tx.run(queries['germplasm']['delete_entries'], entry_ids=entry_ids)

    async def _get_controlled(
            self,
            entry_id: int = None
    ) -> Germplasm | None:
        if entry_id is None:
            try:
                return await anext(self._get_all_controlled())
            except StopAsyncIteration:
                return None

        result = await self.tx.run(queries['germplasm']['read_germplasm'], entry=entry_id)
        nodes = []
        edges = []
        async for record in result:
            entry = self.record_to_entry(record.get('entry'))

            nodes.append(entry)
            for edge in record.get('entry').get('sources', []):
                edges.append(edge)

        if nodes:
            return Germplasm(nodes=nodes, edges=edges)
        else:
            return None

    async def _get_all_controlled(self) -> AsyncGenerator[Germplasm, None]:
        result = await self.tx.run(queries['germplasm']['read_germplasms'])
        async for record in result:
            entries = [self.record_to_entry(entry) for entry in record['germplasm']]
            edges = [edge for entry in record['germplasm'] for edge in entry.get('sources', [])]
            yield Germplasm(nodes=entries, edges=edges)

    async def _remove_controlled(self, germplasm: Germplasm):
        await self._delete_entries([germplasm.root.id])

    async def _update_controlled(self, germplasm: Tracked | Germplasm):
        if not germplasm.changed:
            return

        for node_id in germplasm.graph.added_nodes:
            entry = germplasm.get_entry(node_id)

            if isinstance(entry, GermplasmEntryInput):
                stored_entry = await self._create_entry(entry)
                germplasm.graph.replace_with_stored(node_id, stored_entry)

        if germplasm.graph.removed_nodes:
            await self._delete_entries(list(germplasm.graph.removed_nodes))

        for node_id in germplasm.graph.changed_nodes:

            entry = germplasm.get_entry(node_id)
            if not isinstance(entry, GermplasmEntryStored):
                raise ValueError("Can only commit changes to stored entries")

            await self._update_entry(entry)

        await self._create_edges([(*edge, germplasm.graph.edges[edge]) for edge in germplasm.graph.added_edges])
        await self._delete_edges(germplasm.graph.removed_edges)


    async def _create_edges(self, edges: Set[Tuple[int, int, dict]]):
        if edges:
            await self.tx.run(queries['germplasm']['create_edges'], edges=list(edges))

    async def _delete_edges(self, edges: Set[tuple[int, int]]):
        if edges:
            await self.tx.run(queries['germplasm']['delete_edges'], edges=list(edges))
