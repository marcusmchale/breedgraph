import logging

from neo4j import AsyncResult, Record

from src.breedgraph.domain.model.blocks import (
    UnitInput, UnitStored, Block
)
from src.breedgraph.adapters.neo4j.cypher import queries
from src.breedgraph.adapters.repositories.trackable_wrappers import Tracked
from src.breedgraph.adapters.repositories.controlled import Neo4jControlledRepository

from typing import Set, AsyncGenerator, Tuple, List

logger = logging.getLogger(__name__)

class Neo4jBlocksRepository(Neo4jControlledRepository):

    async def _create_controlled(self, unit: UnitInput) -> Block:
        stored_unit = await self._create_unit(unit)
        return Block(nodes=[stored_unit])

    async def _create_unit(self, unit: UnitInput) -> UnitStored:
        logger.debug(f"Create unit: {unit}")
        result: AsyncResult = await self.tx.run(queries['blocks']['create_unit'], **unit.model_dump())
        record: Record = await result.single()
        return self.record_to_unit(record.get('unit'))

    @staticmethod
    def record_to_unit(record):
        for position in record.get('positions', []):
            Neo4jControlledRepository.times_to_dt64(position)
        return UnitStored(**record)

    async def _update_unit(self, unit: UnitStored):
        logger.debug(f"Set unit: {unit}")
        await self.tx.run(queries['blocks']['set_unit'], unit.model_dump())

    async def _delete_units(self, unit_ids: List[int]) -> None:
        logger.debug(f"Remove units: {unit_ids}")
        await self.tx.run(queries['blocks']['remove_units'], unit_ids=unit_ids)

    async def _get_controlled(self, unit_id: int = None) -> Block | None:
        if unit_id is None:
            try:
                return await anext(self._get_all_controlled())
            except StopAsyncIteration:
                return None

        result: AsyncResult = await self.tx.run( queries['blocks']['read_block'], unit_id=unit_id)

        nodes = []
        edges = []
        async for record in result:
            unit = self.record_to_unit(record.get('unit'))
            nodes.append(unit)
            parent_id = record.get('unit').get('parent_id', None)
            if parent_id is not None:
                edge = (parent_id, unit.id, None)
                edges.append(edge)

        if nodes:
            return Block(nodes=nodes, edges=edges)
        else:
            return None

    async def _get_all_controlled(self, location_id: int|None = None) -> AsyncGenerator[Block, None]:
        if location_id is None:
            result: AsyncResult = await self.tx.run(queries['blocks']['read_blocks'])
        else:
            import pdb; pdb.set_trace()
            # todo filter by location in query (current position only)
            result: AsyncResult = await self.tx.run(queries['blocks']['read_blocks_by_location'])

        async for record in result:
            units = [self.record_to_unit(l) for l in record['block']]
            edges = [(unit.get('parent_id'), unit.get('id'), None) for unit in record.get('block') if unit.get('parent_id') is not None]
            yield Block(nodes=units, edges=edges)

    async def _remove_controlled(self, block: Block) -> None:
        await self._delete_units(list(block.graph.nodes.keys()))

    async def _update_controlled(self, block: Tracked | Block):
        if not block.changed:
            return

        for unit_id in block.graph.added_nodes:
            unit = block.get_entry(unit_id)

            if isinstance(unit, UnitInput):
                stored_unit = await self._create_unit(unit)
                block.graph.replace_with_stored(unit_id, stored_unit)

        if block.graph.removed_nodes:
            await self._delete_units(list(block.graph.removed_nodes))

        for node_id in block.graph.changed_nodes:

            unit = block.get_unit(node_id)
            if not isinstance(unit, UnitStored):
                raise ValueError("Can only commit changes to stored layouts")

            await self._update_unit(unit)

        await self._create_edges(block.graph.added_edges)
        await self._delete_edges(block.graph.removed_edges)

    async def _create_edges(self, edges: Set[Tuple[int, int]]):
        if edges:
            await self.tx.run(queries['blocks']['create_edges'], edges=list(edges))

    async def _delete_edges(self, edges: Set[tuple[int, int]]):
        if edges:
            await self.tx.run(queries['blocks']['delete_edges'], edges=list(edges))

