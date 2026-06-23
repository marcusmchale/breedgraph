from abc import ABC, abstractmethod

from src.breedgraph.domain.model.ontology import Version, OntologyEntryLabel

from src.breedgraph.service_layer.queries.read_models import Ontology, OntologyEntryOutput

from typing import List

class AbstractOntologyView(ABC):

    def __init__(self):
        self._current_version_cache: Version | None = None

    async def get_current_version(self) -> Version:
        if self._current_version_cache is None:
            self._current_version_cache = await self._get_current_version()
        return self._current_version_cache

    @abstractmethod
    async def _get_current_version(self) -> Version:
        ...

    async def get_ontology(self, version: Version | None = None) -> Ontology:
        if version is None:
            version = await self._get_current_version()
        return await self._get_ontology(
            version
        )

    @abstractmethod
    async def _get_ontology(self, version: Version) -> Ontology:
        ...

    """
    Get entries by ID with relationship attributes determined by active relationships at the given version
    """
    async def get_entries(
            self,
            version: Version | None = None,
            entry_ids: List[int] | None = None,
            labels : List[OntologyEntryLabel] | None = None,
            draft: bool = False
    ) -> List[OntologyEntryOutput]:
        # version is needed to appropriately provide the current phase and filter for active relationships
        if version is None:
            version = await self._get_current_version()
        return await self._get_entries(version, entry_ids, labels, draft)

    @abstractmethod
    async def _get_entries(
            self,
            version: Version,
            entry_ids: List[int] | None = None,
            labels: List[OntologyEntryLabel] | None = None,
            draft: bool = False
    ) -> List[OntologyEntryOutput]:
        ...

