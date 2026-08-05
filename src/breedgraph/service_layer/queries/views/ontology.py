from abc import ABC, abstractmethod

from breedgraph.domain.model import LifecyclePhase
from breedgraph.domain.model.ontology import Version, OntologyEntryLabel, OntologyCommit

from breedgraph.service_layer.queries.read_models import (
    Ontology, OntologyEntryOutput, OntologyViewMode, OntologyRelationshipOutput
)

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


    """
    Get relationships for updating the ontology,
     typically just used to update the cache without refetching the whole ontology
    """
    async def get_relationships(
            self,
            entry_ids: list[int],
            version: Version | None = None,
            view: OntologyViewMode = OntologyViewMode.PUBLISHED
    ) -> list[OntologyRelationshipOutput]:
        if version is None:
            version = await self._get_current_version()
        return await self._get_relationships(entry_ids, version, view)

    @abstractmethod
    async def _get_relationships(
            self,
            entry_ids: list[int],
            version: Version,
            view: OntologyViewMode,
    ) -> list[OntologyRelationshipOutput]:
        ...

    async def get_commits(self, limit:int|None = None, last_version_id:int|None = None):
        return await self._get_commits(limit, last_version_id)

    @abstractmethod
    async def _get_commits(
            self,
            limit: int|None = None,
            last_version_id: int|None = None,
    ) -> list[OntologyCommit]:
        ...
