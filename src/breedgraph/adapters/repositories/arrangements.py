import logging

from neo4j import AsyncResult, Record

from src.breedgraph.domain.model.arrangements import (
    LayoutInput, LayoutStored, Arrangement
)
from src.breedgraph.adapters.neo4j.cypher import queries
from src.breedgraph.adapters.repositories.trackable_wrappers import Tracked
from src.breedgraph.adapters.repositories.controlled import Neo4jControlledRepository

from typing import Set, AsyncGenerator, Tuple, List

logger = logging.getLogger(__name__)

class Neo4jArrangementsRepository(Neo4jControlledRepository):

    async def _create_controlled(self, layout: LayoutInput) -> Arrangement:
        stored_layout = await self._create_layout(layout)
        return Arrangement(nodes=[stored_layout])

    async def _create_layout(self, layout: LayoutInput) -> LayoutStored:
        logger.debug(f"Create layout: {layout}")
        result: AsyncResult = await self.tx.run(queries['arrangements']['create_layout'], **layout.model_dump())
        record: Record = await result.single()
        return LayoutStored(**record['layout'])

    async def _update_layout(self, layout: LayoutStored) -> LayoutStored:
        logger.debug(f"Set layout: {layout}")
        result: AsyncResult = await self.tx.run(queries['arrangements']['set_layout'], layout.model_dump())
        record: Record = await result.single()
        return LayoutStored(**record['layout'])

    async def _delete_layouts(self, layout_ids: List[int]) -> None:
        logger.debug(f"Remove layouts: {layout_ids}")
        await self.tx.run(queries['arrangements']['remove_layouts'], layout_ids=layout_ids)

    async def _get_controlled(self, layout_id: int = None) -> Arrangement | None:
        if layout_id is None:
            try:
                return await anext(self._get_all_controlled())
            except StopAsyncIteration:
                return None

        result: AsyncResult = await self.tx.run( queries['arrangements']['read_arrangement'], layout_id=layout_id)

        nodes = []
        edges = []
        async for record in result:
            layout = LayoutStored(**record.get('layout'))
            nodes.append(layout)
            parent_position = record.get('layout').get('parent_position', None)
            if parent_position is not None:
                edge = (parent_position[0], layout.id, {'position': parent_position[1]})
                edges.append(edge)

        if nodes:
            return Arrangement(nodes=nodes, edges=edges)
        else:
            return None

    async def _get_all_controlled(self, location_id: int|None = None) -> AsyncGenerator[Arrangement, None]:
        if location_id is None:
            result: AsyncResult = await self.tx.run(queries['arrangements']['read_arrangements'])
        else:
            result: AsyncResult = await self.tx.run(queries['arrangements']['read_arrangements_by_location'], location_id=location_id)

        async for record in result:
            layouts = [LayoutStored(**l) for l in record['arrangement']]
            edges = [(layout.get('parent_position')[0], layout.get('id'), {'position':layout.get('parent_position')[1]}) for layout in record.get('arrangement') if layout.get('parent_position') is not None]
            yield Arrangement(nodes=layouts, edges=edges)

    async def _remove_controlled(self, arrangement: Arrangement) -> None:
        await self._delete_layouts(list(arrangement._graph.nodes.keys()))

    async def _update_controlled(self, arrangement: Tracked | Arrangement):
        if not arrangement.changed:
            return

        for layout_id in arrangement._graph.added_nodes:
            layout = arrangement.get_entry(layout_id)

            if isinstance(layout, LayoutInput):
                stored_layout = await self._create_layout(layout)
                arrangement._graph.replace_with_stored(layout_id, stored_layout)

        if arrangement._graph.removed_nodes:
            await self._delete_layouts(list(arrangement._graph.removed_nodes))

        for node_id in arrangement._graph.changed_nodes:

            layout = arrangement.get_layout(node_id)
            if not isinstance(layout, LayoutStored):
                raise ValueError("Can only commit changes to stored layouts")

            await self._update_layout(layout)

        await self._create_edges([(*e, arrangement._graph.edges[e]['position']) for e in arrangement._graph.added_edges])
        await self._delete_edges(arrangement._graph.removed_edges)

    async def _create_edges(self, edges: Set[Tuple[int, int, int|str|tuple]]):
        if edges:
            await self.tx.run(queries['arrangements']['create_edges'], edges=list(edges))

    async def _delete_edges(self, edges: Set[tuple[int, int]]):
        if edges:
            await self.tx.run(queries['arrangements']['delete_edges'], edges=list(edges))

