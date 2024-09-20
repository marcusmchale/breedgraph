import logging

from neo4j import AsyncResult, Record

from src.breedgraph.domain.model.regions import (
    Region, LocationInput, LocationStored
)
from src.breedgraph.adapters.neo4j.cypher import queries
from src.breedgraph.adapters.repositories.trackable_wrappers import Tracked, TrackedList, TrackedDict
from src.breedgraph.adapters.repositories.controlled import Neo4jControlledRepository

from typing import Set, AsyncGenerator, Tuple, List

logger = logging.getLogger(__name__)

class Neo4jRegionsRepository(Neo4jControlledRepository):

    async def _create_controlled(self, location: LocationInput) -> Region:
        async for region in self._get_all_controlled():
            if location.name.casefold() in [name.casefold for name in region.root.names]:
                raise ValueError("This name is in use for the root on an existing region")
            if region.root.code is not None:
                if region.root.code.casefold() == location.code.casefold():
                    raise ValueError("This code is in use for the root on an existing region")

        stored_location = await self._create_location(location)
        return Region(nodes=[stored_location])

    async def _create_location(self, location: LocationInput) -> LocationStored:
        logger.debug(f"Create location: {location}")
        result: AsyncResult = await self.tx.run(queries['regions']['create_location'], **location.model_dump())
        record: Record = await result.single()
        return LocationStored(**record['location'])

    async def _update_location(self, location: LocationStored):
        logger.debug(f"Set location: {location}")
        await self.tx.run(queries['regions']['set_location'], location.model_dump())

    async def _delete_locations(self, location_ids: List[int]) -> None:
        logger.debug(f"Remove locations: {location_ids}")
        await self.tx.run(queries['regions']['remove_locations'], location_ids=location_ids)

    async def _get_controlled(self, location_id: int = None) -> Region | None:
        if location_id is None:
            try:
                return await anext(self._get_all_controlled())
            except StopAsyncIteration:
                return None

        result: AsyncResult = await self.tx.run( queries['regions']['read_region'], location_id=location_id)

        nodes = []
        edges = []
        async for record in result:
            location = LocationStored(**record.get('location'))
            nodes.append(location)
            parent_id = record.get('location').get('parent_id', None)
            if parent_id is not None:
                edges.append((parent_id, location.id, None))

        if nodes:
            return Region(nodes=nodes, edges=edges)
        else:
            return None

    async def _get_all_controlled(self) -> AsyncGenerator[Region, None]:
        result: AsyncResult = await self.tx.run(queries['regions']['read_regions'])
        async for record in result:
            locations = [LocationStored(**l) for l in record['region']]
            edges = [
                (entry.get('parent_id'), entry.get('id'), None) for entry in record['region'] if entry.get('parent_id') is not None
            ]
            yield Region(nodes=locations, edges=edges)

    async def _remove_controlled(self, region: Region) -> None:
        await self._delete_locations(list(region.graph.nodes.keys()))

    async def _update_controlled(self, region: Tracked | Region):
        if not region.changed:
            return

        for location_id in region.graph.added_nodes:
            location = region.get_entry(location_id)

            if isinstance(location, LocationInput):
                stored_location = await self._create_location(location)
                region.graph.replace_with_stored(location_id, stored_location)

        if region.graph.removed_nodes:
            await self._delete_locations(list(region.graph.removed_nodes))

        for node_id in region.graph.changed_nodes:

            location = region.get_location(node_id)
            if not isinstance(location, LocationStored):
                raise ValueError("Can only commit changes to stored locations")

            await self._update_location(location)

        await self._create_edges(region.graph.added_edges)
        await self._delete_edges(region.graph.removed_edges)

    async def _create_edges(self, edges: Set[Tuple[int, int]]):
        if edges:
            await self.tx.run(queries['regions']['create_edges'], edges=list(edges))

    async def _delete_edges(self, edges: Set[tuple[int, int]]):
        if edges:
            await self.tx.run(queries['regions']['delete_edges'], edges=list(edges))


