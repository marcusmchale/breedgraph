import logging
from numpy import datetime64
from neo4j import AsyncResult, Record

from breedgraph.domain.model.unit_graphs import (
    UnitInput, UnitStored, UnitGraph, Position
)
from breedgraph.adapters.neo4j.cypher import queries
from breedgraph.service_layer.tracking import TrackableProtocol
from breedgraph.service_layer.repositories.controlled import ControlledQueryResult
from breedgraph.adapters.neo4j.repositories.controlled import Neo4jControlledRepository

from typing import Set, AsyncGenerator, Tuple, List, Dict, Any

logger = logging.getLogger(__name__)

class Neo4jUnitGraphsRepository(Neo4jControlledRepository[UnitInput, UnitGraph]):

    @staticmethod
    def position_sort_key(position: Position):
        start = position.start
        end = position.end

        if start is None and end is None:
            return (0, datetime64("NaT", "D"))

        return (1, start if start is not None else end)


    async def _create_controlled(self, unit: UnitInput) -> UnitGraph:
        stored_unit = await self._create_unit(unit)
        return UnitGraph(nodes=[stored_unit])

    async def _create_unit(self, unit: UnitInput) -> UnitStored:
        logger.debug(f"Create unit: {unit}")
        unit_data = unit.model_dump()
        for position in unit_data.get('positions', []):
            self.serialize_dt64(position, to_neo4j=True)
        result: AsyncResult = await self.tx.run(queries['unit_graphs']['create_unit'], **unit_data)
        record: Record = await result.single()
        return self.record_to_unit(record.get('unit'))

    def record_to_unit(self, record):
        for position in record.get('positions', []):
            self.deserialize_dt64(position)
        record['positions'] = [Position(**position) for position in record.get('positions', [])]
        record['positions'].sort(key=self.position_sort_key)

        return UnitStored(**record)

    async def _update_unit(self, unit: UnitStored):
        logger.debug(f"Set unit: {unit}")
        unit_data = unit.model_dump()
        # positions are written outside the unit graph (application.unit_positions), as only new units' are here
        unit_data.pop('positions', None)
        await self.tx.run(queries['unit_graphs']['set_unit'], **unit_data)

    async def _delete_units(self, unit_ids: List[int]) -> None:
        logger.debug(f"Remove units: {unit_ids}")
        await self.tx.run(queries['unit_graphs']['delete_units'], unit_ids=unit_ids)

    async def _get_controlled(self, unit_id: int|None = None) -> ControlledQueryResult[UnitGraph]|None:
        if unit_id is None:
            try:
                return await anext(self._get_all_controlled())
            except StopAsyncIteration:
                return None

        result: AsyncResult = await self.tx.run( queries['unit_graphs']['read_unit_graph'], unit_id=unit_id)

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
            return ControlledQueryResult(UnitGraph(nodes=nodes, edges=edges))
        else:
            return None

    async def _get_all_controlled(
            self,
            location_ids: List[int]|None = None,
            unit_ids: List[int]|None = None
    ) -> AsyncGenerator[ControlledQueryResult[UnitGraph]|None, None]:
        if unit_ids:
            result: AsyncResult = await self.tx.run(
                queries['unit_graphs']['read_unit_graphs_by_unit_ids'],
                unit_ids = unit_ids
            )
        elif location_ids:
            result: AsyncResult = await self.tx.run(
                queries['unit_graphs']['read_unit_graphs_by_locations'],
                location_ids = location_ids
            )
        else:
            result: AsyncResult = await self.tx.run(queries['unit_graphs']['read_unit_graphs'])
        async for record in result:
            units_data = record.get('unit_graph')
            edges = []
            for unit_data in units_data:
                parent_ids = unit_data.pop('parent_ids')
                if parent_ids is not None:
                    for parent_id in parent_ids:
                        edges.append((parent_id, unit_data.get('id'), None))
            units = [self.record_to_unit(u) for u in units_data]
            yield ControlledQueryResult(UnitGraph(nodes=units, edges=edges))

    async def _remove_controlled(self, unit_graph: UnitGraph) -> None:
        await self._delete_units(list(unit_graph._graph.nodes.keys()))

    async def _update_controlled(self, unit_graph: TrackableProtocol | UnitGraph):
        if not unit_graph.changed:
            return

        for unit_id in unit_graph._graph.added_nodes:
            unit = unit_graph.get_entry(unit_id)

            if isinstance(unit, UnitInput):
                stored_unit = await self._create_unit(unit)
                unit_graph._graph.replace_with_stored(unit_id, stored_unit)

        if unit_graph._graph.removed_nodes:
            await self._delete_units(list(unit_graph._graph.removed_nodes))

        for node_id in unit_graph._graph.changed_nodes:

            unit = unit_graph.get_unit(node_id)
            if not isinstance(unit, UnitStored):
                raise ValueError("Can only commit changes to stored layouts")
            await self._update_unit(unit)

        to_remove = unit_graph._graph.removed_edges - unit_graph._graph.added_edges
        to_add = unit_graph._graph.added_edges - unit_graph._graph.removed_edges
        await self._create_edges(to_add)
        await self._delete_edges(to_remove)

    async def _create_edges(self, edges: Set[Tuple[int, int]]):
        if edges:
            await self.tx.run(queries['unit_graphs']['create_edges'], edges=list(edges))

    async def _delete_edges(self, edges: Set[tuple[int, int]]):
        if edges:
            await self.tx.run(queries['unit_graphs']['delete_edges'], edges=list(edges))

