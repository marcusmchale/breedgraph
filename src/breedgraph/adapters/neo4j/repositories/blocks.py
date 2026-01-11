import logging

from neo4j import AsyncResult, Record

from src.breedgraph.domain.model.blocks import (
    UnitInput, UnitStored, Block, Position
)
from src.breedgraph.adapters.neo4j.cypher import queries
from src.breedgraph.service_layer.tracking import TrackableProtocol
from src.breedgraph.adapters.neo4j.repositories.controlled import Neo4jControlledRepository

from typing import Set, AsyncGenerator, Tuple, List, Dict, Any

logger = logging.getLogger(__name__)

class Neo4jBlocksRepository(Neo4jControlledRepository[UnitStored, Block]):

    async def _create_controlled(self, unit: UnitInput) -> Block:
        stored_unit = await self._create_unit(unit)
        return Block(nodes=[stored_unit])

    async def _create_unit(self, unit: UnitInput) -> UnitStored:
        logger.debug(f"Create unit: {unit}")
        unit_data = unit.model_dump()
        for position in unit_data.get('positions', []):
            self.serialize_dt64(position, to_neo4j=True)
        result: AsyncResult = await self.tx.run(queries['blocks']['create_unit'], **unit_data)
        record: Record = await result.single()
        return self.record_to_unit(record.get('unit'))

    def record_to_unit(self, record):
        for position in record.get('positions', []):
            self.deserialize_dt64(position)
        record['positions'] = [Position(**position) for position in record.get('positions', [])]
        return UnitStored(**record)

    async def _update_unit(self, unit: UnitStored):
        logger.debug(f"Set unit: {unit}")
        unit_data = unit.model_dump()
        for position in unit_data.get('positions', []):
            self.serialize_dt64(position, to_neo4j=True)
        await self.tx.run(queries['blocks']['set_unit'], **unit_data)

    async def _delete_units(self, unit_ids: List[int]) -> None:
        logger.debug(f"Remove units: {unit_ids}")
        await self.tx.run(queries['blocks']['delete_units'], unit_ids=unit_ids)

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
            parent_ids = record.get('unit').pop('parent_ids', None)
            unit = self.record_to_unit(record.get('unit'))
            nodes.append(unit)
            if parent_ids is not None:
                for parent_id in parent_ids:
                    edge = (parent_id, unit.id, None)
                    edges.append(edge)

        if nodes:
            return Block(nodes=nodes, edges=edges)
        else:
            return None

    async def _get_all_controlled(self, location_ids: List[int]|None = None) -> AsyncGenerator[Block, None]:
        if not location_ids:
            result: AsyncResult = await self.tx.run(queries['blocks']['read_blocks'])
        else:
            result: AsyncResult = await self.tx.run(
                queries['blocks']['read_blocks_by_locations'],
                location_ids = location_ids
            )
        async for record in result:
            units_data = record.get('block')
            edges = []
            for unit_data in units_data:
                parent_ids = unit_data.pop('parent_ids')
                if parent_ids is not None:
                    for parent_id in parent_ids:
                        edges.append((parent_id, unit_data.get('id'), None))
            units = [self.record_to_unit(u) for u in units_data]
            yield Block(nodes=units, edges=edges)

    async def _remove_controlled(self, block: Block) -> None:
        await self._delete_units(list(block._graph.nodes.keys()))

    async def _update_controlled(self, block: TrackableProtocol | Block):
        if not block.changed:
            return

        for unit_id in block._graph.added_nodes:
            unit = block.get_entry(unit_id)

            if isinstance(unit, UnitInput):
                stored_unit = await self._create_unit(unit)
                block._graph.replace_with_stored(unit_id, stored_unit)

        if block._graph.removed_nodes:
            await self._delete_units(list(block._graph.removed_nodes))

        for node_id in block._graph.changed_nodes:

            unit = block.get_unit(node_id)
            if not isinstance(unit, UnitStored):
                raise ValueError("Can only commit changes to stored layouts")
            await self._update_unit(unit)

        to_remove = block._graph.removed_edges - block._graph.added_edges
        to_add = block._graph.added_edges - block._graph.removed_edges
        await self._create_edges(to_add)
        await self._delete_edges(to_remove)

    async def _create_edges(self, edges: Set[Tuple[int, int]]):
        if edges:
            await self.tx.run(queries['blocks']['create_edges'], edges=list(edges))

    async def _delete_edges(self, edges: Set[tuple[int, int]]):
        if edges:
            await self.tx.run(queries['blocks']['delete_edges'], edges=list(edges))

