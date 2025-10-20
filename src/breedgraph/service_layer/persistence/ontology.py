import re
from abc import ABC, abstractmethod
from functools import lru_cache

from typing import List, Set, Optional, Dict, Any, Tuple, AsyncGenerator, Type

from src.breedgraph.domain.model.ontology import OntologyMapper, OntologyEntryBase
from src.breedgraph.domain.model.ontology.version import VersionChange
from src.breedgraph.domain.model.ontology.entries import (
    OntologyEntryInput, OntologyEntryStored, OntologyEntryOutput
)
from src.breedgraph.domain.model.ontology.relationships import OntologyRelationshipBase
from src.breedgraph.domain.model.ontology.enums import OntologyRelationshipLabel, OntologyEntryLabel
from src.breedgraph.domain.model.ontology.lifecycle import LifecyclePhase, EntryLifecycle, RelationshipLifecycle
from src.breedgraph.domain.model.ontology.version import Version, OntologyCommit
from src.breedgraph.domain.model.ontology.mappers import OntologyMapper, ontology_mapper

import logging
logger = logging.getLogger(__name__)


# NOTE this is strange but..
# for async generator abstract methods we need to define them as sync functions for typing to work
# https://stackoverflow.com/questions/68905848/how-to-correctly-specify-type-hints-with-asyncgenerator-and-asynccontextmanager


class OntologyPersistenceService(ABC):
    """
    Streamlined persistence service that handles both data operations and validation queries.
    Consolidates all persistence-related functionality needed by the application service.
    """
    ontology_mapper: OntologyMapper = ontology_mapper

    async def create_entry(
            self,
            entry: OntologyEntryInput,
            user_id: int
    ) -> OntologyEntryStored:
        """Create a new ontology entry and return it in stored form (with ID)."""
        logger.debug(f"Creating entry: {entry.name} ({entry.label})")
        return await self._create_entry(entry, user_id)

    @abstractmethod
    async def entries_exist(self, entry_ids: List[int]) -> Dict[int, bool]:
        ...

    @abstractmethod
    async def entries_exist_for_label(self, entry_ids: List[int], label: OntologyEntryLabel) -> Dict[int, bool]:
        ...

    @abstractmethod
    async def get_current_version(self):
        ...

    @abstractmethod
    async def _create_entry(self, entry: OntologyEntryInput, user_id: int) -> OntologyEntryStored:
        ...

    @abstractmethod
    async def get_entry(
            self,
            entry_id: int = None,
            name: str = None,
            label: OntologyEntryLabel = None,
            as_output: bool = False
    )-> OntologyEntryStored|OntologyEntryOutput|None:
        """Retrieve an ontology entry"""
        ...

    @abstractmethod
    async def update_entry(self, entry: OntologyEntryStored, user_id: int) -> None:
        """Update an existing ontology entry."""
        ...

    @abstractmethod
    async def create_relationship(self, relationship: OntologyRelationshipBase) -> OntologyRelationshipBase:
        """Create a new relationship between entries."""
        ...

    @abstractmethod
    async def update_relationship(self, relationship: OntologyRelationshipBase) -> None:
        """Update attributes of an existing relationship."""
        ...

    @abstractmethod
    def get_entries(
            self,
            version: Version|None = None,
            phases: List[LifecyclePhase] | None = None,
            entry_ids: List[int] = None,
            labels: List[OntologyEntryLabel]|None = None,
            names: List[str]|None = None,
            as_output: bool = False,
    ) -> AsyncGenerator[OntologyEntryStored|OntologyEntryOutput, None]:
        """
        Retrieve ontology entries
          optionally filter by version/phase/label/name
          and optionally return in output format which includes relationships (default: stored)
         """
        ...

    @abstractmethod
    def get_relationships(
            self,
            version: Version | None = None,
            phases: List[LifecyclePhase] | None = None,
            labels: List[OntologyRelationshipLabel] | None = None,
            entry_ids: List[int] = None,
            source_ids: List[int] = None,
            target_ids: List[int] = None
    ) -> AsyncGenerator[OntologyRelationshipBase, None]:
        """
        Retrieve ontology relationships,
            optionally filter by version/phase/label/entry_id
        :return:
        """
        ...

    @abstractmethod
    async def get_entry_lifecycles(self, entry_ids: List[int]) -> Dict[int, EntryLifecycle]:
        ...

    @abstractmethod
    async def get_relationship_lifecycles(self, relationship_ids: List[int]) -> Dict[int, RelationshipLifecycle]:
        ...

    # Lifecycle persistence
    @abstractmethod
    async def save_entry_lifecycles(self, lifecycles: Dict[int, EntryLifecycle], user_id: int) -> None:
        """Save entry lifecycles to persistent storage."""
        ...

    @abstractmethod
    async def activate_drafts(self, version: Version):
        ...

    @abstractmethod
    async def remove_deprecated(self, version: Version):
        ...

    @abstractmethod
    async def save_relationship_lifecycles(
        self,
        lifecycles: Dict[int, RelationshipLifecycle],
        user_id: int
    ) -> None:
        """Save relationship lifecycles to persistent storage."""
        ...

    # Validation query methods
    @abstractmethod
    async def name_in_use(
        self,
        label: OntologyEntryLabel,
        name: str,
        exclude_id: int|None = None
    ) -> bool:
        """Return a boolean whether the name is in use for a specific entry type."""
        ...

    @abstractmethod
    async def abbreviation_in_use(
        self,
        label: OntologyEntryLabel,
        abbreviation: str,
        exclude_id: int|None = None
    ) -> bool:
        """Return a boolean whether the abbreviation is in use for a specific entry type."""
        ...

    @abstractmethod
    async def get_entry_types(self, entry_ids: List[int]) -> Dict[int, str]:
        """Get the types/labels of multiple entries."""
        ...

    @abstractmethod
    async def has_path_between_entries(
        self,
        source_id: int,
        target_id: int,
        relationship_type: OntologyRelationshipLabel
    ) -> bool:
        """Check if there's a path between two entries (for cycle detection)."""
        ...

    @abstractmethod
    async def get_entry_dependencies(self, entry_id: int) -> List[int]:
        """Get all entries that depend on this entry (incoming relationships)."""
        ...


    async def commit_version(
            self,
            user_id: int,
            version_change: VersionChange,
            comment: str = None,
            licence_reference: int = None,
            copyright_reference: int = None
    ) -> OntologyCommit:
        current_version = await self.get_current_version()
        version = current_version.increment(version_change)
        commit = OntologyCommit(
            version = version,
            comment=comment,
            licence=licence_reference,
            copyright=copyright_reference
        )
        """Save version with commit metadata."""
        await self._commit_version(user_id, commit)
        return commit

    @abstractmethod
    async def _commit_version(self, user_id: int, commit: OntologyCommit):
        ...

    @abstractmethod
    def get_commits(self, version_min: Version = None, version_max: Version = None) -> AsyncGenerator[OntologyCommit,None]:
        """Get version by ID."""
        ...

    @abstractmethod
    def get_commit_history(self, limit: int = 10) -> AsyncGenerator[OntologyCommit, None]:
        """Get version history ordered by commit time."""
        ...
