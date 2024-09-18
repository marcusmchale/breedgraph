import logging

from neo4j import AsyncResult, Record
from numpy import datetime64
from collections import defaultdict

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
        unit_records = defaultdict(list)
        for r in dataset_dict['unit_records']:
            unit_records[r[0]] += r[1]
        dataset_dict['unit_records'] = unit_records
        for unit_id, records in dataset_dict['unit_records'].items():
            for record in records:
                if 'start' in record:
                    record['start'] = datetime64(record['start'], (record['start_unit'], record['start_step']))
                if 'end' in record:
                    record['end'] = datetime64(record['end'], (record['end_unit'], record['end_step']))
        return DataSetStored(**dataset_dict)

    async def _create_dataset(self, dataset: DataSetInput) -> DataSetStored:
        logger.debug(f"Create dataset: {dataset}")
        params = dataset.model_dump()
        params['unit_records'] = [(unit, records) for unit, records in params.get('unit_records', {}).items()]
        result: AsyncResult = await self.tx.run(queries['datasets']['create_dataset'], **params)
        record: Record = await result.single()
        return self.record_to_dataset(record.get('dataset'))

    async def _update_dataset(self, dataset: DataSetStored|Tracked):
        if dataset.changed - {'unit_records', 'controller'}:
            logger.debug(f"Set dataset: {dataset}")
            params = dataset.model_dump()
            params.pop('unit_records')
            await self.tx.run(queries['datasets']['set_dataset'], params)

        if 'unit_records' in dataset.changed:
            to_create = defaultdict(list)  # unit_records structure, but just for new inputs
            to_remove = list()  # list of record IDs to delete

            # todo, could allow for adding contributors or references without removal,
            #  but this is more than we need to handle right now

            for unit_id in dataset.unit_records.removed:
                to_remove += [r.id for r in dataset.unit_records[unit_id]]
            if to_remove:
                await self.tx.run(queries['datasets']['delete_records'], record_ids=to_remove)

            # changes are removed and will be created again, any changes make a new record.
            for unit_id in dataset.unit_records.changed:
                records = dataset.unit_records[unit_id]
                for i in records.added:
                    to_create[unit_id].append(records[i])
                for i in records.changed:
                    to_remove.append(i)
                    to_create.append(records[i])
                for r in records.removed:
                    to_remove.append(r.id)

                # remove the added in reverse index order
                for i in sorted(records.added, reverse=True):
                    del records[i]

            # entirely new references to unit_id should be fine to add to created and clear
            for unit_id in dataset.unit_records.added:
                to_create[unit_id] += dataset.unit_records[unit_id]
                dataset.unit_records[unit_id].clear()
                dataset.unit_records[unit_id].reset_tracking()

            to_create = [(unit, [record.model_dump() for record in records]) for unit, records in to_create.items()]
            result = await self.tx.run(queries['datasets']['create_records'], dataset_id=dataset.id, unit_records=to_create)
            # add the created records back in
            async for record in result:
                unit_id = record.get('unit_id')
                records = record.get('records')
                for r in records:
                    dataset.unit_records[unit_id].append(DataRecordStored(**r))

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




