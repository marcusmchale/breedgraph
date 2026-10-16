import logging

from neo4j import AsyncResult, Record

from breedgraph.custom_exceptions import IdentityExistsError
from breedgraph.domain.model.location_trees import (
    LocationTree, LocationInput, LocationStored
)
from breedgraph.adapters.neo4j.cypher import queries
from breedgraph.service_layer.tracking import TrackableProtocol
from breedgraph.domain.model.controls import DiscoveryMatch
from breedgraph.service_layer.repositories.controlled import ControlledQueryResult
from breedgraph.adapters.neo4j.repositories.controlled import Neo4jControlledRepository
from breedgraph.adapters.neo4j.cypher.matching import exact_text_regex

from typing import Set, AsyncGenerator, Tuple, List

logger = logging.getLogger(__name__)

class Neo4jLocationTreesRepository(Neo4jControlledRepository[LocationInput, LocationTree]):

    async def _create_controlled(self, location: LocationInput) -> LocationTree:
        # Only location tree roots (countries) must be unique; locations within location trees may share names
        async for _ in self._get_all_controlled(location.name, location.code):
            raise IdentityExistsError("A location tree root location with this name or code is already registered")
        stored_location = await self._create_location(location)
        return LocationTree(nodes=[stored_location])

    async def _create_location(self, location: LocationInput) -> LocationStored:
        logger.debug(f"Create location: {location}")
        result: AsyncResult = await self.tx.run(queries['location_trees']['create_location'], **location.model_dump())
        record: Record = await result.single()
        return LocationStored(**record['location'])

    async def _update_location(self, location: LocationStored):
        logger.debug(f"Set location: {location}")
        await self.tx.run(queries['location_trees']['set_location'], location.model_dump())

    async def _delete_locations(self, location_ids: List[int]) -> None:
        logger.debug(f"Remove locations: {location_ids}")
        await self.tx.run(queries['location_trees']['delete_locations'], location_ids=location_ids)

    async def _get_controlled(self, location_id: int|None = None, name: str|None = None, code:str|None = None) -> ControlledQueryResult[LocationTree] | None:
        if location_id:
            result: AsyncResult = await self.tx.run( queries['location_trees']['read_location_tree'], location_id=location_id)
            nodes = []
            edges = []
            async for record in result:
                parent_id = record.get('location').pop('parent_id', None)
                location = LocationStored(**record.get('location'))
                nodes.append(location)
                if parent_id is not None:
                    edges.append((parent_id, location.id, None))

            if nodes:
                return ControlledQueryResult(LocationTree(nodes=nodes, edges=edges))
            else:
                return None
        else:
            try:
                return await anext(self._get_all_controlled(name=name, code=code))
            except StopAsyncIteration:
                return None

    @staticmethod
    def record_to_location_tree(record) -> LocationTree:
        edges = []
        for entry in record['location_tree']:
            parent_id = entry.pop('parent_id', None)
            if parent_id is not None:
                edges.append((parent_id, entry.get('id'), None))
        locations = [LocationStored(**l) for l in record['location_tree']]
        return LocationTree(nodes=locations, edges=edges)

    async def _get_all_controlled(self, name:str|None = None, code:str|None = None) -> AsyncGenerator[ControlledQueryResult[LocationTree], None]:
        if name is None and code is None:
            result: AsyncResult = await self.tx.run(queries['location_trees']['read_location_trees'])
            async for record in result:
                yield  ControlledQueryResult(self.record_to_location_tree(record))
        else:
            result = await self.tx.run(
                queries['location_trees']['get_location_trees_by_root_name_or_code'],
                name_regex=exact_text_regex(name) if name is not None else None,
                # case insensitive matching won't use indices, so use sparingly
                code_regex=exact_text_regex(code) if code is not None else None
            )
            async for record in result:
                yield ControlledQueryResult(self.record_to_location_tree(record), matches=tuple(DiscoveryMatch(**m) for m in record.get('matches')))

    async def _remove_controlled(self, location_tree: LocationTree) -> None:
        await self._delete_locations(list(location_tree._graph.nodes.keys()))

    async def _update_controlled(self, location_tree: TrackableProtocol | LocationTree):
        if not location_tree.changed:
            return

        for location_id in location_tree._graph.added_nodes:
            location = location_tree.get_entry(location_id)

            if isinstance(location, LocationInput):
                stored_location = await self._create_location(location)
                location_tree._graph.replace_with_stored(location_id, stored_location)

        if location_tree._graph.removed_nodes:
            await self._delete_locations(list(location_tree._graph.removed_nodes))

        for node_id in location_tree._graph.changed_nodes:

            location = location_tree.get_location(node_id)
            if not isinstance(location, LocationStored):
                raise ValueError("Can only commit changes to stored locations")

            await self._update_location(location)

        # here, we remove removed from added and added from removed to ensure that changes that are
        # both added and removed are not affected by the order of processing,
        # i.e. if both are done then no change is made.
        await self._create_edges(location_tree._graph.added_edges - location_tree._graph.removed_edges)
        await self._delete_edges(location_tree._graph.removed_edges - location_tree._graph.added_edges)

    async def _create_edges(self, edges: Set[Tuple[int, int]]):
        if edges:
            await self.tx.run(queries['location_trees']['create_edges'], edges=list(edges))

    async def _delete_edges(self, edges: Set[tuple[int, int]]):
        if edges:
            await self.tx.run(queries['location_trees']['delete_edges'], edges=list(edges))


