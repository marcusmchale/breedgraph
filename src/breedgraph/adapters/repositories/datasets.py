import logging

from neo4j import AsyncResult, Record

from src.breedgraph.domain.model.datasets import (
    DataRecordStored, DataSetInput, DataSetStored
)

from src.breedgraph.adapters.neo4j.cypher import queries
from src.breedgraph.adapters.repositories.trackable_wrappers import Tracked, TrackedList, TrackedDict
from src.breedgraph.adapters.repositories.controlled import Neo4jControlledRepository

from typing import AsyncGenerator, List

logger = logging.getLogger(__name__)

class Neo4jDatasetsRepository(Neo4jControlledRepository):

    async def _create_controlled(self, dataset: DataSetInput) -> DataSetStored:
        return await self._create_dataset(dataset)

    @staticmethod
    def record_to_dataset(dataset_dict):
        for record in dataset_dict['records']:
            Neo4jDatasetsRepository.times_to_dt64(record)
        return DataSetStored(**dataset_dict)

    async def _create_dataset(self, dataset: DataSetInput) -> DataSetStored:
        logger.debug(f"Create dataset: {dataset}")
        params = dataset.model_dump()
        params['unit_records'] = [(unit, records) for unit, records in params.get('unit_records', {}).items()]
        result: AsyncResult = await self.tx.run(queries['datasets']['create_dataset'], **params)
        record: Record = await result.single()
        return self.record_to_dataset(record.get('dataset'))

    async def _update_dataset(self, dataset: DataSetStored|Tracked):
        if dataset.changed - {'records', 'controller'}:
            logger.debug(f"Set dataset: {dataset}")
            params = dataset.model_dump()
            params.pop('records')
            await self.tx.run(queries['datasets']['set_dataset'], params)

        if 'records' in dataset.changed:
            if dataset.records.changed:
                await self.tx.run(
                    queries['datasets']['set_records'],
                    records=[dataset.records[i].model_dump() for i in dataset.records.changed]
                )

        if dataset.records.removed:
            await self.tx.run(
                queries['datasets']['delete_records'],
                record_ids=[r.id for r in dataset.records.removed]
            )

        if dataset.records.added:
            ordered_added = list(dataset.records.added)
            result = await self.tx.run(
                queries['datasets']['create_records'],
                dataset_id=dataset.id,
                records=[dataset.records[i].model_dump() for i in ordered_added]
            )
            i = 0
            async for r in result:
                record = r.get('record')
                Neo4jControlledRepository.times_to_dt64(record)
                record_index = ordered_added[i]
                dataset.records[record_index] = DataRecordStored(**record)
                i += 1

    async def _delete_datasets(self, dataset_ids: List[int]) -> None:
        logger.debug(f"Remove datasets: {dataset_ids}")
        await self.tx.run(queries['datasets']['remove_datasets'], dataset_ids=dataset_ids)

    async def _get_controlled(
            self, dataset_id: int = None
    ) -> DataSetStored | None:
        if dataset_id is not None:
            result: AsyncResult = await self.tx.run( queries['datasets']['read_dataset'], dataset_id=dataset_id)
        else:
            try:
                return await anext(self._get_all_controlled())
            except StopAsyncIteration:
                return None
        record = await result.single()
        return self.record_to_dataset(record.get('dataset'))

    async def _get_all_controlled(self, term_id: int = None) -> AsyncGenerator[DataSetStored, None]:
        if term_id is not None:
            result: AsyncResult = await self.tx.run(queries['datasets']['read_datasets_for_term'], term_id=term_id)
        else:
            result: AsyncResult = await self.tx.run(queries['datasets']['read_datasets'])

        async for record in result:
            yield self.record_to_dataset(record.get('dataset'))

    async def _remove_controlled(self, dataset: DataSetStored) -> None:
        await self._delete_datasets([dataset.id])

    async def _update_controlled(self, dataset: Tracked | DataSetStored):
        await self._update_dataset(dataset)
