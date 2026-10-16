import logging

from neo4j import AsyncResult, Record

from breedgraph.domain.model.controls import ControlledModelLabel, DiscoveryMatch
from breedgraph.domain.model.layout_trees import (
    LayoutInput, LayoutStored, LayoutTree
)
from breedgraph.adapters.neo4j.cypher import queries
from breedgraph.service_layer.tracking import TrackableProtocol, TrackedObject
from breedgraph.service_layer.repositories.controlled import ControlledQueryResult
from breedgraph.adapters.neo4j.repositories.controlled import Neo4jControlledRepository

from typing import Set, AsyncGenerator, Tuple, List, Dict, Any, Union, overload

logger = logging.getLogger(__name__)

class Neo4jLayoutTreesRepository(
    Neo4jControlledRepository[LayoutInput, LayoutTree]
):

    @staticmethod
    def record_to_layout(record: Record|Dict[str, Any]) -> LayoutStored:
        if isinstance(record, Record):
            record = dict(record)
        if 'layout' in record:
            record = record.get('layout')
        return LayoutStored(**record)

    async def _create_controlled(self, layout: LayoutInput) -> LayoutTree:
        stored_layout = await self._create_layout(layout)
        return LayoutTree(nodes=[stored_layout])

    async def _create_layout(self, layout: LayoutInput) -> LayoutStored:
        logger.debug(f"Create layout: {layout}")
        result: AsyncResult = await self.tx.run(queries['layout_trees']['create_layout'], **layout.model_dump())
        record: Record = await result.single()
        return self.record_to_layout(record)

    async def _update_layout(self, layout: LayoutStored) -> None:
        logger.debug(f"Set layout: {layout}")
        await self.tx.run(queries['layout_trees']['set_layout'], layout.model_dump())

    async def _delete_layouts(self, layout_ids: List[int]) -> None:
        logger.debug(f"Remove layouts: {layout_ids}")
        await self.tx.run(queries['layout_trees']['delete_layouts'], layout_ids=layout_ids)

    async def _get_controlled(self, layout_id: int|None = None) -> ControlledQueryResult[LayoutTree]|None:
        if layout_id is None:
            try:
                return await anext(self._get_all_controlled())
            except StopAsyncIteration:
                return None

        result: AsyncResult = await self.tx.run( queries['layout_trees']['read_layout_tree'], layout_id=layout_id)

        nodes = []
        edges = []
        async for record in result:
            layout_record = record.get('layout')
            parent_position = layout_record.pop('parent_position') if 'parent_position' in layout_record else None
            if parent_position is not None:
                edge = (parent_position[0], layout_record.get('id'), {'position': parent_position[1]})
                edges.append(edge)
            layout = self.record_to_layout(layout_record)
            nodes.append(layout)

        if nodes:
            return ControlledQueryResult(LayoutTree(nodes=nodes, edges=edges))
        else:
            return None

    async def _get_all_controlled(self, location_id: int|None = None) -> AsyncGenerator[ControlledQueryResult[LayoutTree], None]:
        if location_id is None:
            result: AsyncResult = await self.tx.run(queries['layout_trees']['read_layout_trees'])
        else:
            result: AsyncResult = await self.tx.run(queries['layout_trees']['read_layout_trees_by_location'], location_id=location_id)

        async for record in result:
            layouts = []
            edges = []
            matches = []
            for layout_data in record.get('layout_tree'):
                if 'parent_position' in layout_data:
                    edge_data = layout_data.pop('parent_position')
                    if edge_data is not None:
                        edges.append((edge_data[0], layout_data.get('id'), {'position':edge_data[1]}))
                layout = self.record_to_layout(layout_data)
                layouts.append(layout)
                matches.append(DiscoveryMatch(label=ControlledModelLabel.LAYOUT, model_id=layout.id, key='location_id'))
            yield ControlledQueryResult(LayoutTree(nodes=layouts, edges=edges), matches=tuple(matches))

    async def _remove_controlled(self, layout_tree: LayoutTree) -> None:
        await self._delete_layouts(list(layout_tree._graph.nodes.keys()))

    async def _update_controlled(self, layout_tree: TrackableProtocol | LayoutTree):
        if not layout_tree.changed:
            return

        for layout_id in layout_tree._graph.added_nodes:
            layout = layout_tree.get_entry(layout_id)

            if isinstance(layout, LayoutInput):
                stored_layout = await self._create_layout(layout)
                layout_tree._graph.replace_with_stored(layout_id, stored_layout)

        if layout_tree._graph.removed_nodes:
            await self._delete_layouts(list(layout_tree._graph.removed_nodes))

        for node_id in layout_tree._graph.changed_nodes:

            layout = layout_tree.get_layout(node_id)
            if not isinstance(layout, LayoutStored):
                raise ValueError("Can only commit changes to stored layouts")

            await self._update_layout(layout)

        await self._delete_edges(layout_tree._graph.removed_edges)
        await self._create_edges([(*e, layout_tree._graph.edges[e]['position']) for e in layout_tree._graph.added_edges])

    async def _create_edges(self, edges: Set[Tuple[int, int, list[int|str|tuple]]]):
        if edges:
            await self.tx.run(queries['layout_trees']['create_edges'], edges=list(edges))

    async def _delete_edges(self, edges: Set[tuple[int, int]]):
        if edges:
            await self.tx.run(queries['layout_trees']['delete_edges'], edges=list(edges))
