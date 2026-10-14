from neo4j import AsyncSession, AsyncResult

from breedgraph.service_layer.queries.views import AbstractDatasetsView
from breedgraph.service_layer.queries.read_models import DatasetSummary

from breedgraph.domain.model.controls import ReadRelease
from breedgraph.adapters.neo4j.cypher import queries
from breedgraph.service_layer.queries.read_models import DatasetRead, DatasetDimensions, GroupingCodes
from breedgraph.domain.model.time_descriptors import npdt64_to_neo4j, deserialize_time
from numpy import datetime64
from breedgraph.service_layer.repositories.base import BaseRepository

from typing import List


class Neo4jDatasetsView(AbstractDatasetsView):

    def __init__(self, session: AsyncSession, user_id: int|None, read_teams: List[int]):
        self.session = session
        self.user_id = user_id
        self.read_teams = read_teams

    @staticmethod
    def record_to_dict(record: dict) -> dict:
        BaseRepository.deserialize_dt64(record)
        return {
            'id': record.get('id'),
            'unit': record.get('unit'),
            'value': record.get('value'),
            'start': record.get('start'),
            'end': record.get('end'),
            'groups': [{'id': group['id'], 'code': group['code']} for group in record.get('groups') or []],
            'references': record.get('references') or [],
            'submitted': record.get('submitted')
        }

    async def _get_datasets(
            self,
            dataset_ids: List[int] | None = None,
            study_ids: List[int] | None = None,
            concept_ids: List[int] | None = None
    ) -> List[DatasetRead]:
        async with await self.session.begin_transaction() as tx:
            result: AsyncResult = await tx.run(
                queries['datasets']['read_datasets_for_read_teams'],
                dataset_ids=dataset_ids,
                study_ids=study_ids,
                concept_ids=concept_ids,
                read_teams=self.read_teams,
                minimum_release=int(ReadRelease.PUBLIC if self.user_id is None else ReadRelease.REGISTERED)
            )
            return [DatasetRead(**record['dataset']) async for record in result]

    async def _get_records(
            self,
            dataset_id: int,
            unit_ids: List[int] | None,
            start: datetime64 | None,
            end: datetime64 | None,
            offset: int,
            limit: int | None
    ) -> List[dict]:
        async with await self.session.begin_transaction() as tx:
            result: AsyncResult = await tx.run(
                queries['datasets']['read_dataset_records'],
                dataset_id=dataset_id,
                unit_ids=unit_ids,
                start=npdt64_to_neo4j(datetime64(start)) if start is not None else None,
                end=npdt64_to_neo4j(datetime64(end)) if end is not None else None,
                offset=offset,
                limit=limit if limit is not None else 2 ** 31 - 1
            )
            return [self.record_to_dict(record['record']) async for record in result]

    async def _get_unit_ids(
            self,
            dataset_id: int,
            unit_ids: List[int] | None,
            start: datetime64 | None,
            end: datetime64 | None
    ) -> List[int]:
        async with await self.session.begin_transaction() as tx:
            result: AsyncResult = await tx.run(
                queries['datasets']['read_dataset_unit_ids'],
                dataset_id=dataset_id,
                unit_ids=unit_ids,
                start=npdt64_to_neo4j(datetime64(start)) if start is not None else None,
                end=npdt64_to_neo4j(datetime64(end)) if end is not None else None
            )
            record = await result.single()
            return list(record['unit_ids']) if record else []

    async def _count_records(
            self,
            dataset_id: int,
            unit_ids: List[int] | None,
            start: datetime64 | None,
            end: datetime64 | None
    ) -> int:
        async with await self.session.begin_transaction() as tx:
            result: AsyncResult = await tx.run(
                queries['datasets']['count_dataset_records'],
                dataset_id=dataset_id,
                unit_ids=unit_ids,
                start=npdt64_to_neo4j(datetime64(start)) if start is not None else None,
                end=npdt64_to_neo4j(datetime64(end)) if end is not None else None
            )
            record = await result.single()
            return record['record_count'] if record else 0

    async def _get_dimensions(self, dataset_id: int) -> DatasetDimensions:
        async with await self.session.begin_transaction() as tx:
            result: AsyncResult = await tx.run(
                queries['datasets']['read_dataset_dimensions'],
                dataset_id=dataset_id
            )
            record = await result.single()
        if not record:
            return DatasetDimensions(record_count=0, unit_count=0)
        dimensions = record['dimensions']
        return DatasetDimensions(
            record_count=dimensions['record_count'],
            unit_count=dimensions['unit_count'],
            start=dimensions['start'],
            end=dimensions['end'],
            # percentile times have no stored precision, so they are given to the second, as naive UTC like the records
            time_percentiles=[
                datetime64(deserialize_time(time).replace(tzinfo=None), 's') for time in dimensions['time_percentiles']
            ],
            value_percentiles=list(dimensions['value_percentiles']),
            groups=[GroupingCodes(grouping_id=group['grouping_id'], codes=list(group['codes'])) for group in dimensions['groups']]
        )

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
