from neo4j import AsyncSession, AsyncResult

from breedgraph.service_layer.queries.views import AbstractDatasetsView
from breedgraph.service_layer.queries.read_models import DatasetSummary

from breedgraph.domain.model.controls import ReadRelease
from breedgraph.adapters.neo4j.cypher import queries

from typing import List


class Neo4jDatasetsView(AbstractDatasetsView):

    def __init__(self, session: AsyncSession, user_id: int|None, read_teams: List[int]):
        self.session = session
        self.user_id = user_id
        self.read_teams = read_teams

    async def _get_dataset_summaries(self, study_id: int) -> List[DatasetSummary]:
        async with await self.session.begin_transaction() as tx:
            result: AsyncResult = await tx.run(
                queries['datasets']['get_dataset_summaries_for_read_teams'],
                study_id=study_id,
                read_teams = self.read_teams,
                minimum_release = ReadRelease.PUBLIC if self.user_id is None else ReadRelease.REGISTERED
            )
            return [
                DatasetSummary(**record.get('dataset_summary')) async for record in result
            ]
