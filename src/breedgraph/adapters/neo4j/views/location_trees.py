from neo4j import AsyncResult, AsyncSession

from breedgraph.service_layer.queries.views.location_trees import AbstractLocationTreesView
from breedgraph.service_layer.infrastructure.state_store import AbstractStateStore

from breedgraph.adapters.neo4j.cypher import queries
from breedgraph.adapters.neo4j.cypher.query_builders import location_trees as location_tree_queries

from breedgraph.domain.model.location_trees import LocationOutput
from breedgraph.domain.model.controls import ReadRelease

from typing import List, Dict, AsyncGenerator

class Neo4jLocationTreesView(AbstractLocationTreesView):
    def __init__(
            self,
            state_store: AbstractStateStore,
            user_id: int | None,
            read_teams: List[int],
            session: AsyncSession
    ):
        self.state_store = state_store
        self.user_id = user_id
        self.read_teams: List[int] = read_teams
        self.session = session

    @property
    def _minimum_release(self) -> ReadRelease:
        return ReadRelease.REGISTERED if self.user_id is not None else ReadRelease.PUBLIC

    async def _read(self, query: str, **params) -> List[LocationOutput]:
        result: AsyncResult = await self.session.run(
            query, **params, read_teams=self.read_teams, minimum_release=self._minimum_release
        )
        return [LocationOutput(**record['location']) async for record in result]

    async def _get_location_trees(self) -> List[LocationOutput]:
        return await self._read(location_tree_queries.read_location_trees())

    async def _get_locations(self, location_ids: List[int]) -> Dict[int, LocationOutput]:
        locations = await self._read(location_tree_queries.read_locations(), location_ids=location_ids)
        return {location.id: location for location in locations}

    async def _get_locations_by_type(self, location_type_id: int) -> AsyncGenerator[LocationOutput, None]:
        for location in await self._read(location_tree_queries.read_locations_by_type(), location_type=location_type_id):
            yield location

    async def _get_descendants_by_type(self, location_ids: List[int]) -> Dict[int | None, List[LocationOutput]]:
        async with await self.session.begin_transaction() as tx:
            result: AsyncResult = await tx.run(
                location_tree_queries.read_descendants_by_type(),
                location_ids=location_ids,
                read_teams=self.read_teams,
                minimum_release=ReadRelease.REGISTERED if self.user_id is not None else ReadRelease.PUBLIC
            )
            return {
                record['type']: [
                    LocationOutput(id=location['id'], name=location['name'], type=record['type'])
                    for location in record['locations']
                ]
                async for record in result
            }