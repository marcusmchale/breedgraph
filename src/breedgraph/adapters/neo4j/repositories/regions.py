import logging

from neo4j import AsyncResult, Record

from src.breedgraph.domain.model.regions import (
    Region, LocationInput, LocationStored
)
from src.breedgraph.adapters.neo4j.cypher import queries
from src.breedgraph.service_layer.tracking import TrackableProtocol
from src.breedgraph.adapters.neo4j.repositories.controlled import Neo4jControlledRepository

from typing import Set, AsyncGenerator, Tuple, List

logger = logging.getLogger(__name__)

class Neo4jRegionsRepository(Neo4jControlledRepository[LocationInput, Region]):

    async def _create_controlled(self, location: LocationInput) -> Region:
        stored_location = await self._create_location(location)
        return Region(nodes=[stored_location])

    async def _create_location(self, location: LocationInput) -> LocationStored:
        logger.debug(f"Create location: {location}")
        async for _ in self._get_all_controlled(location.name, location.code):
            raise ValueError("A region root location with this name or code is already registered")
        result: AsyncResult = await self.tx.run(queries['regions']['create_location'], **location.model_dump())
        record: Record = await result.single()
        return LocationStored(**record['location'])

    async def _update_location(self, location: LocationStored):
        logger.debug(f"Set location: {location}")
        await self.tx.run(queries['regions']['set_location'], location.model_dump())

    async def _delete_locations(self, location_ids: List[int]) -> None:
        logger.debug(f"Remove locations: {location_ids}")
        await self.tx.run(queries['regions']['delete_locations'], location_ids=location_ids)

    async def _get_controlled(self, location_id: int = None) -> Region | None:
        if location_id:
            result: AsyncResult = await self.tx.run( queries['regions']['read_region'], location_id=location_id)
            nodes = []
            edges = []
            async for record in result:
                parent_id = record.get('location').pop('parent_id', None)
                location = LocationStored(**record.get('location'))
                nodes.append(location)
                if parent_id is not None:
                    edges.append((parent_id, location.id, None))

            if nodes:
                return Region(nodes=nodes, edges=edges)
            else:
                return None
        else:
            try:
                return await anext(self._get_all_controlled())
            except StopAsyncIteration:
                return None

    @staticmethod
    def record_to_region(record) -> Region:
        edges = []
        for entry in record['region']:
            parent_id = entry.pop('parent_id', None)
            if parent_id is not None:
                edges.append((parent_id, entry.get('id'), None))
        locations = [LocationStored(**l) for l in record['region']]
        return Region(nodes=locations, edges=edges)

    async def _get_all_controlled(self, name=None, code=None) -> AsyncGenerator[Region, None]:
        if name is None and code is None:
            result: AsyncResult = await self.tx.run(queries['regions']['read_regions'])
        else:
            result = await self.tx.run(
                queries['regions']['get_regions_by_root_name_or_code'],
                name_regex=f"(?i)^{name}$",
                # case insensitive matching won't use indices, so use sparingly
                code_regex=f"(?i)^{code}$"
            )
        async for record in result:
            yield self.record_to_region(record)

    async def _remove_controlled(self, region: Region) -> None:
        await self._delete_locations(list(region._graph.nodes.keys()))

    async def _update_controlled(self, region: TrackableProtocol | Region):
        if not region.changed:
            return

        for location_id in region._graph.added_nodes:
            location = region.get_entry(location_id)

            if isinstance(location, LocationInput):
                stored_location = await self._create_location(location)
                region._graph.replace_with_stored(location_id, stored_location)

        if region._graph.removed_nodes:
            await self._delete_locations(list(region._graph.removed_nodes))

        for node_id in region._graph.changed_nodes:

            location = region.get_location(node_id)
            if not isinstance(location, LocationStored):
                raise ValueError("Can only commit changes to stored locations")

            await self._update_location(location)

        # here, we remove removed from added and added from removed to ensure that changes that are
        # both added and removed are not affected by the order of processing,
        # i.e. if both are done then no change is made.
        await self._create_edges(region._graph.added_edges - region._graph.removed_edges)
        await self._delete_edges(region._graph.removed_edges - region._graph.added_edges)

    async def _create_edges(self, edges: Set[Tuple[int, int]]):
        if edges:
            await self.tx.run(queries['regions']['create_edges'], edges=list(edges))

    async def _delete_edges(self, edges: Set[tuple[int, int]]):
        if edges:
            await self.tx.run(queries['regions']['delete_edges'], edges=list(edges))


