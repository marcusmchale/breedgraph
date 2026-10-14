from abc import ABC, abstractmethod

from breedgraph.service_layer.queries.read_models import DatasetSummary, DatasetRead
from numpy import datetime64

from typing import List, AsyncGenerator

class AbstractDatasetsView(ABC):
    user_id: int|None
    read_teams: List[int]

    async def get_dataset_summaries(self, study_id: int) -> List[DatasetSummary]:
        return await self._get_dataset_summaries(study_id=study_id)

    @abstractmethod
    async def _get_dataset_summaries(self, study_id: int) -> List[DatasetSummary]:
        ...

    async def get_datasets(
            self,
            dataset_ids: List[int] | None = None,
            study_ids: List[int] | None = None,
            concept_ids: List[int] | None = None
    ) -> List[DatasetRead]:
        """
        Dataset headers selected by any combination of ids, studies and concepts (no selection means all of them),
        read without building the aggregate. Datasets the user cannot read come back with readable False and no
        contributors or references, as the repository returns them to registered users; their records are not read.
        """
        return await self._get_datasets(dataset_ids=dataset_ids, study_ids=study_ids, concept_ids=concept_ids)

    async def get_records(
            self,
            dataset_id: int,
            unit_ids: List[int] | None = None,
            start: datetime64 | None = None,
            end: datetime64 | None = None,
            offset: int = 0,
            limit: int | None = None
    ) -> List[dict]:
        """A page of a readable dataset's records in submission order, as dicts with the record fields"""
        if unit_ids is not None:
            unit_ids = [unit_id for unit_id in dict.fromkeys(unit_ids) if unit_id is not None]
        return await self._get_records(dataset_id=dataset_id, unit_ids=unit_ids, start=start, end=end, offset=max(offset or 0, 0), limit=limit)

    @abstractmethod
    async def _get_datasets(
            self,
            dataset_ids: List[int] | None = None,
            study_ids: List[int] | None = None,
            concept_ids: List[int] | None = None
    ) -> List[DatasetRead]:
        ...

    @abstractmethod
    async def _get_records(
            self,
            dataset_id: int,
            unit_ids: List[int] | None,
            start: datetime64 | None,
            end: datetime64 | None,
            offset: int,
            limit: int | None
    ) -> List[dict]:
        ...
