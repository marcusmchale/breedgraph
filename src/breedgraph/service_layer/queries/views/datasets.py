from abc import ABC, abstractmethod

from breedgraph.service_layer.queries.read_models import DatasetSummary
from breedgraph.domain.model.datasets import DatasetOutput

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
    ) -> List[DatasetOutput]:
        """
        Datasets selected by any combination of ids, studies and concepts (no selection means all of them),
        read without building the aggregate. Datasets the user cannot read are returned without records,
        contributors or references, as the repository returns them to registered users.
        """
        return await self._get_datasets(dataset_ids=dataset_ids, study_ids=study_ids, concept_ids=concept_ids)

    @abstractmethod
    async def _get_datasets(
            self,
            dataset_ids: List[int] | None = None,
            study_ids: List[int] | None = None,
            concept_ids: List[int] | None = None
    ) -> List[DatasetOutput]:
        ...

