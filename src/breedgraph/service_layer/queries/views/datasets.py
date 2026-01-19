from abc import ABC, abstractmethod

from src.breedgraph.service_layer.queries.read_models import DatasetSummary

from typing import List, AsyncGenerator

class AbstractDatasetsView(ABC):
    read_teams: List[int]

    async def get_dataset_summaries(self, study_id: int) -> List[DatasetSummary]:
        return await self._get_dataset_summaries(study_id=study_id)

    @abstractmethod
    async def _get_dataset_summaries(self, study_id: int) -> List[DatasetSummary]:
        ...
