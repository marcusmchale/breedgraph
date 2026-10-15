from neo4j import AsyncSession, AsyncResult

from breedgraph.service_layer.queries.views import AbstractDatasetsView
from breedgraph.service_layer.queries.read_models import DatasetSummary

from breedgraph.domain.model.controls import ReadRelease
from breedgraph.adapters.neo4j.cypher import queries
from breedgraph.adapters.neo4j.cypher.query_builders import datasets as dataset_queries
from breedgraph.adapters.neo4j.cypher.query_builders.datasets import (
    SUMMARY_FIELDS,
    UNIT_FIELDS,
    dataset_summaries as dataset_summaries_query,
    dataset_unit_summaries as dataset_unit_summaries_query
)
from breedgraph.service_layer.queries.read_models import DatasetRead, DatasetDimensions, GroupingCodes, DatasetsUnit
from breedgraph.domain.model.blocks import UnitOutput
from breedgraph.domain.model.time_descriptors import npdt64_to_neo4j, deserialize_time
from numpy import datetime64
from datetime import datetime

from typing import List, Dict, AbstractSet


class Neo4jDatasetsView(AbstractDatasetsView):
    """The read checks and placeholders are in the Cypher (see query_builders.datasets)"""

    def __init__(self, session: AsyncSession, user_id: int|None, read_teams: List[int]):
        self.session = session
        self.user_id = user_id
        self.read_teams = read_teams

    @property
    def _access(self) -> dict:
        """The parameters of the read checks"""
        return {
            'read_teams': self.read_teams,
            'minimum_release': int(ReadRelease.PUBLIC if self.user_id is None else ReadRelease.REGISTERED)
        }

    @staticmethod
    def _record_time(text: str | None, unit: str | None, step: int | None) -> datetime64 | None:
        """A record's start or end, read as UTC text (see query_builders.datasets.read_records), at its precision"""
        if text is None:
            return None
        return datetime64(text, (unit, step))

    @classmethod
    def record_to_dict(cls, record: dict) -> dict:
        submitted = record.get('submitted')
        return {
            'id': record.get('id'),
            'unit': record.get('unit'),
            'value': record.get('value'),
            'start': cls._record_time(record.get('start'), record.get('start_unit'), record.get('start_step')),
            'end': cls._record_time(record.get('end'), record.get('end_unit'), record.get('end_step')),
            'groups': [{'id': group['id'], 'code': group['code']} for group in record.get('groups') or []],
            'references': record.get('references') or [],
            # the transaction's timestamp, timezone aware
            'submitted': datetime.fromisoformat(submitted) if submitted is not None else None
        }

    async def _get_datasets(
            self,
            dataset_ids: List[int] | None = None,
            study_ids: List[int] | None = None,
            concept_ids: List[int] | None = None
    ) -> List[DatasetRead]:
        async with await self.session.begin_transaction() as tx:
            result: AsyncResult = await tx.run(
                dataset_queries.read_datasets(),
                dataset_ids=dataset_ids,
                study_ids=study_ids,
                concept_ids=concept_ids,
                **self._access
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
                dataset_queries.read_records(),
                dataset_id=dataset_id,
                unit_ids=unit_ids,
                start=npdt64_to_neo4j(datetime64(start)) if start is not None else None,
                end=npdt64_to_neo4j(datetime64(end)) if end is not None else None,
                offset=offset,
                limit=limit if limit is not None else 2 ** 31 - 1,
                **self._access
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
                dataset_queries.read_unit_ids(),
                dataset_id=dataset_id,
                unit_ids=unit_ids,
                start=npdt64_to_neo4j(datetime64(start)) if start is not None else None,
                end=npdt64_to_neo4j(datetime64(end)) if end is not None else None,
                **self._access
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
                dataset_queries.count_records(),
                dataset_id=dataset_id,
                unit_ids=unit_ids,
                start=npdt64_to_neo4j(datetime64(start)) if start is not None else None,
                end=npdt64_to_neo4j(datetime64(end)) if end is not None else None,
                **self._access
            )
            record = await result.single()
            return record['record_count'] if record else 0

    async def _get_unit_level(
            self,
            dataset_ids: List[int],
            parent_ids: List[int] | None,
            start: datetime64 | None,
            end: datetime64 | None
    ) -> List[DatasetsUnit]:
        async with await self.session.begin_transaction() as tx:
            result: AsyncResult = await tx.run(
                dataset_queries.read_unit_level(),
                dataset_ids=dataset_ids,
                parent_ids=parent_ids,
                start=npdt64_to_neo4j(datetime64(start)) if start is not None else None,
                end=npdt64_to_neo4j(datetime64(end)) if end is not None else None,
                **self._access
            )
            return [
                DatasetsUnit(
                    id=record['id'],
                    unit_count=record['unit_count'],
                    record_count=record['record_count'],
                    has_children=record['has_children']
                ) async for record in result
            ]

    async def _get_units_by_subject(
            self,
            dataset_ids: List[int],
            unit_ids: List[int] | None,
            start: datetime64 | None,
            end: datetime64 | None
    ) -> Dict[int | None, List[UnitOutput]]:
        async with await self.session.begin_transaction() as tx:
            result: AsyncResult = await tx.run(
                dataset_queries.read_units_by_subject(),
                dataset_ids=dataset_ids,
                unit_ids=unit_ids,
                start=npdt64_to_neo4j(datetime64(start)) if start is not None else None,
                end=npdt64_to_neo4j(datetime64(end)) if end is not None else None,
                **self._access
            )
            return {
                record['subject']: [
                    UnitOutput(id=unit['id'], name=unit['name'], subject=record['subject']) for unit in record['units']
                ]
                async for record in result
            }

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

    async def _get_dataset_summaries(
            self,
            study_id: int,
            fields: AbstractSet[str] | None = None
    ) -> List[DatasetSummary]:
        fields = SUMMARY_FIELDS if fields is None else frozenset(fields)
        async with await self.session.begin_transaction() as tx:
            result: AsyncResult = await tx.run(
                dataset_summaries_query(fields),
                study_id=study_id,
                **self._access
            )
            summaries = {record['dataset_summary']['id']: record['dataset_summary'] async for record in result}
            if summaries and fields & UNIT_FIELDS:
                result = await tx.run(dataset_unit_summaries_query(fields), dataset_ids=list(summaries), **self._access)
                async for record in result:
                    unit_summary = record['unit_summary']
                    summaries[unit_summary['id']].update(unit_summary)
                # a dataset without records has no units
                if 'unit_count' in fields:
                    for summary in summaries.values():
                        summary.setdefault('unit_count', 0)
            return [DatasetSummary(**summary) for summary in summaries.values()]
