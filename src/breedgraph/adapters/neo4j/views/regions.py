from neo4j import AsyncResult, AsyncSession

from src.breedgraph.service_layer.queries.views.regions import AbstractRegionsView
from src.breedgraph.service_layer.infrastructure.state_store import AbstractStateStore

from src.breedgraph.adapters.neo4j.cypher import queries
from src.breedgraph.adapters.neo4j.driver import Neo4jAsyncDriver


from src.breedgraph.domain.model.regions import LocationOutput

from typing import List, AsyncGenerator

class Neo4jRegionsView(AbstractRegionsView):
    def __init__(
            self,
            state_store: AbstractStateStore,
            read_teams: List[int],
            session: AsyncSession
    ):
        self.state_store = state_store
        self.read_teams: List[int] = read_teams
        self.session = session

    async def _get_locations_by_type(self, location_type_id: int) -> AsyncGenerator[LocationOutput, None]:
        async with await self.session.begin_transaction() as tx:
            result: AsyncResult = await tx.run(
                queries['regions']['get_locations_by_type_for_read_teams'],
                location_type=location_type_id,
                read_teams=self.read_teams
            )
            async for record in result:
                yield LocationOutput(**record['location'])