from abc import ABC, abstractmethod

from breedgraph.domain.model import LifecyclePhase
from breedgraph.domain.model.ontology import Version, OntologyEntryLabel

from breedgraph.service_layer.queries.read_models import Ontology, OntologyEntryOutput, OntologyViewMode

class AbstractOntologyView(ABC):
    DEFAULT_PHASES = [LifecyclePhase.ACTIVE]

    def __init__(self):
        self._current_version_cache: Version | None = None

    async def get_current_version(self) -> Version|None:
        if self._current_version_cache is None:
            self._current_version_cache = await self._get_current_version()
        return self._current_version_cache

    @abstractmethod
    async def _get_current_version(self) -> Version:
        ...

    async def get_ontology(
            self,
            version: Version | None = None,
            view: OntologyViewMode = OntologyViewMode.PUBLISHED

    ) -> Ontology:
        if version is None:
            version = await self._get_current_version()
        return await self._get_ontology(
            version,
            view
        )

    @abstractmethod
    async def _get_ontology(self, version: Version, view: OntologyViewMode) -> Ontology:
        ...

    """
    Get entries by ID with relationship attributes
    """
    async def get_entries(
            self,
            version: Version | None = None,
            view: OntologyViewMode = OntologyViewMode.PUBLISHED,
            entry_ids: list[int] | None = None,
            labels : list[OntologyEntryLabel] | None = None
    ) -> list[OntologyEntryOutput]:
        if version is None:
            version = await self._get_current_version()
        return await self._get_entries(version, view, entry_ids, labels)

    @abstractmethod
    async def _get_entries(
            self,
            version: Version,
            view: OntologyViewMode,
            entry_ids: list[int] | None = None,
            labels: list[OntologyEntryLabel] | None = None
    ) -> list[OntologyEntryOutput]:
        ...

