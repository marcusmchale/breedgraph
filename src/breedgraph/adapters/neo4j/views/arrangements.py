from neo4j import AsyncResult, AsyncSession

from breedgraph.adapters.neo4j.cypher.query_builders import arrangements as arrangement_queries
from breedgraph.domain.model.arrangements import LayoutOutput
from breedgraph.domain.model.controls import ReadRelease
from breedgraph.service_layer.queries.views.arrangements import AbstractArrangementsView

from typing import List, Dict


class Neo4jArrangementsView(AbstractArrangementsView):

    def __init__(self, session: AsyncSession, user_id: int | None, read_teams: List[int]):
        self.session = session
        self.user_id = user_id
        self.read_teams = read_teams

    async def _read(self, query: str, **params) -> List[LayoutOutput]:
        result: AsyncResult = await self.session.run(
            query,
            **params,
            read_teams=self.read_teams,
            minimum_release=ReadRelease.REGISTERED if self.user_id is not None else ReadRelease.PUBLIC
        )
        return [LayoutOutput(**record['layout']) async for record in result]

    async def _get_arrangements(self, location_id: int) -> List[LayoutOutput]:
        return await self._read(arrangement_queries.read_arrangements(), location_id=location_id)

    async def _get_layouts(self, layout_ids: List[int]) -> Dict[int, LayoutOutput]:
        layouts = await self._read(arrangement_queries.read_layouts(), layout_ids=layout_ids)
        return {layout.id: layout for layout in layouts}
