import logging

from neo4j import AsyncResult, Record

from src.breedgraph.domain.model.datasets import (
    DataRecordStored, DatasetInput, DatasetStored
)

from src.breedgraph.adapters.neo4j.cypher import queries
from src.breedgraph.service_layer.tracking import TrackableProtocol
from src.breedgraph.service_layer.repositories.controlled import ControlledQueryResult
from src.breedgraph.adapters.neo4j.repositories.controlled import Neo4jControlledRepository


from typing import AsyncGenerator, List

logger = logging.getLogger(__name__)

class Neo4jDatasetsRepository(Neo4jControlledRepository[DatasetInput, DatasetStored]):

    async def _create_controlled(self, dataset: DatasetInput) -> DatasetStored:
        return await self._create_dataset(dataset)

    def record_to_dataset(self, dataset_dict):
        for record in dataset_dict['records']:
            self.deserialize_dt64(record)
        dataset_dict['records'] = [DataRecordStored(**record) for record in dataset_dict['records']]
        return DatasetStored(**dataset_dict)

    async def _create_dataset(self, dataset: DatasetInput) -> DatasetStored:
        logger.debug(f"Create dataset: {dataset}")
        params = dataset.model_dump()
        records = params.pop('records', [])
        result: AsyncResult = await self.tx.run(queries['datasets']['create_dataset'], **params)
        dataset_record: Record = await result.single()
        if records:
            for record_data in records:
                self.serialize_dt64(record_data, to_neo4j=True)
            result = await self.tx.run(
                queries['datasets']['create_records'],
                dataset_id=dataset_record.get('dataset').get('id'),
                records=records
            )
            dataset_record_dict = dataset_record.data()
            dataset_record_dict['records'] = [record.get('record') async for record in result]
        dataset = self.record_to_dataset(dataset_record.get('dataset'))
        return dataset


    async def _update_dataset(self, dataset: DatasetStored|TrackableProtocol):
        if dataset.changed - {'records', 'controller'}:
            logger.debug(f"Set dataset: {dataset}")
            params = dataset.model_dump()
            await self.tx.run(queries['datasets']['set_dataset'], params)

        if 'records' in dataset.changed:
            if dataset.records.changed:
                changed_records = [
                    self.serialize_dt64(dataset.records[i].model_dump(), to_neo4j=True) for i in dataset.records.changed
                ]
                await self.tx.run(
                    queries['datasets']['set_records'],
                    records=changed_records
                )

            if dataset.records.removed:
                await self.tx.run(
                    queries['datasets']['delete_records'],
                    record_ids=[r.id for r in dataset.records.removed]
                )

            if dataset.records.added:
                ordered_added = list(dataset.records.added)
                added_records = [self.serialize_dt64(dataset.records[i].model_dump(), to_neo4j=True) for i in ordered_added]
                result = await self.tx.run(
                    queries['datasets']['create_records'],
                    dataset_id=dataset.id,
                    records=added_records
                )
                i = 0
                async for r in result:
                    record = r.get('record')
                    self.deserialize_dt64(record)
                    record_index = ordered_added[i]
                    dataset.records[record_index] = DataRecordStored(**record)
                    i += 1

    async def _delete_datasets(self, dataset_ids: List[int]) -> None:
        logger.debug(f"Remove datasets: {dataset_ids}")
        await self.tx.run(queries['datasets']['remove_datasets'], dataset_ids=dataset_ids)

    async def _get_controlled(
            self,
            dataset_id: int|None = None
    ) -> ControlledQueryResult[DatasetStored] | None:
        if dataset_id is not None:
            result: AsyncResult = await self.tx.run( queries['datasets']['read_dataset'], dataset_id=dataset_id)
        else:
            try:
                return await anext(self._get_all_controlled())
            except StopAsyncIteration:
                return None
        record = await result.single(strict=True)
        return ControlledQueryResult(self.record_to_dataset(record.get('dataset')))

    async def _get_all_controlled(
            self,
            study_ids: List[int]|None = None,
            dataset_ids: List[int]|None = None,
            concept_ids: List[int]|None = None
    ) -> AsyncGenerator[ControlledQueryResult[DatasetStored], None]:

        if study_ids is not None:
            if concept_ids is not None:
                result: AsyncResult = await self.tx.run(
                    queries['datasets']['read_datasets_for_studies_and_concepts'],
                    study_ids=study_ids,
                    concept_ids=concept_ids
                )
            else:
                result: AsyncResult = await self.tx.run(
                    queries['datasets']['read_datasets_for_studies'],
                    study_ids=study_ids
                )
        elif concept_ids is not None:
            result: AsyncResult = await self.tx.run(
                queries['datasets']['read_datasets_for_concepts'],
                concept_ids=concept_ids
            )
        elif dataset_ids is not None:
            result: AsyncResult = await self.tx.run(
                queries['datasets']['read_datasets_by_id'],
                dataset_ids=dataset_ids
            )


        else:
            result: AsyncResult = await self.tx.run(queries['datasets']['read_datasets'])

        async for record in result:
            yield ControlledQueryResult(self.record_to_dataset(record.get('dataset')))

    async def _remove_controlled(self, dataset: DatasetStored) -> None:
        await self._delete_datasets([dataset.id])

    async def _update_controlled(self, dataset: TrackableProtocol | DatasetStored):
        await self._update_dataset(dataset)
