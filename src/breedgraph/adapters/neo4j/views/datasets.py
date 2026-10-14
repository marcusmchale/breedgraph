from neo4j import AsyncSession, AsyncResult

from breedgraph.service_layer.queries.views import AbstractDatasetsView
from breedgraph.service_layer.queries.read_models import DatasetSummary

from breedgraph.domain.model.controls import ReadRelease
from breedgraph.adapters.neo4j.cypher import queries
from breedgraph.domain.model.datasets import DatasetOutput
from breedgraph.service_layer.repositories.base import BaseRepository

from typing import List


class Neo4jDatasetsView(AbstractDatasetsView):

    def __init__(self, session: AsyncSession, user_id: int|None, read_teams: List[int]):
        self.session = session
        self.user_id = user_id
        self.read_teams = read_teams

    @staticmethod
    def record_to_dataset(dataset: dict) -> DatasetOutput:
        dataset.pop('readable', None)
        records = []
        for record in dataset.get('records') or []:
            BaseRepository.deserialize_dt64(record)
            records.append({
                'id': record.get('id'),
                'unit': record.get('unit'),
                'value': record.get('value'),
                'start': record.get('start'),
                'end': record.get('end'),
                'groups': [{'id': group['id'], 'code': group['code']} for group in record.get('groups') or []],
                'references': record.get('references') or [],
                'submitted': record.get('submitted')
            })
        dataset['records'] = records
        return DatasetOutput(**dataset)

    async def _get_datasets(
            self,
            dataset_ids: List[int] | None = None,
            study_ids: List[int] | None = None,
            concept_ids: List[int] | None = None
    ) -> List[DatasetOutput]:
        async with await self.session.begin_transaction() as tx:
            result: AsyncResult = await tx.run(
                queries['datasets']['read_datasets_for_read_teams'],
                dataset_ids=dataset_ids,
                study_ids=study_ids,
                concept_ids=concept_ids,
                read_teams=self.read_teams,
                minimum_release=int(ReadRelease.PUBLIC if self.user_id is None else ReadRelease.REGISTERED)
            )
            return [self.record_to_dataset(record['dataset']) async for record in result]

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
