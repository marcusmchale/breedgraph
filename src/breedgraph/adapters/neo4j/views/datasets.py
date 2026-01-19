from neo4j import AsyncSession, AsyncResult

from src.breedgraph.service_layer.queries.views import AbstractDatasetsView
from src.breedgraph.service_layer.queries.read_models import DatasetSummary

from src.breedgraph.adapters.neo4j.cypher import queries

from typing import List


class Neo4jDatasetsView(AbstractDatasetsView):

    def __init__(self, session: AsyncSession, read_teams: List[int]):
        self.session = session
        self.read_teams = read_teams

    async def _get_dataset_summaries(self, study_id: int) -> List[DatasetSummary]:
        async with await self.session.begin_transaction() as tx:
            result: AsyncResult = await tx.run(
                queries['datasets']['get_dataset_summaries_for_read_teams'],
                study_id=study_id,
                read_teams = self.read_teams
            )
            return [
                DatasetSummary(**record.get('dataset_summary')) async for record in result
            ]
