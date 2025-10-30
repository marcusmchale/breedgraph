from abc import ABC, abstractmethod
from typing import List, Set, Optional, Dict, Any, Tuple, AsyncGenerator

from src.breedgraph.domain.model.germplasm import (
    GermplasmInput, GermplasmStored, GermplasmSourceType, Reproduction, GermplasmRelationship
)

import logging
logger = logging.getLogger(__name__)

class GermplasmPersistenceService(ABC):
    """
    Persistence service for germplasm operations.
    Handles data operations and validation queries for germplasm entries.
    """

    async def create_entry(self, entry: GermplasmInput) -> GermplasmStored:
        """Create a new germplasm entry and return it in stored form (with ID)."""
        logger.debug(f"Creating germplasm entry: {entry.name}")
        return await self._create_entry(entry)

    @abstractmethod
    async def _create_entry(self, entry: GermplasmInput) -> GermplasmStored:
        raise NotImplementedError

    @abstractmethod
    async def get_entry(self, entry_id: int) -> Optional[GermplasmStored]:
        """Retrieve a germplasm entry by ID."""
        pass

    @abstractmethod
    async def update_entry(self, entry: GermplasmStored) -> None:
        """Update an existing germplasm entry."""
        pass

    @abstractmethod
    async def delete_entry(self, entry_id: int):
        pass

    @abstractmethod
    def get_root_entries(self) -> AsyncGenerator[GermplasmStored, None]:
        """Retrieve all germplasm entries that have no parents."""
        pass

    @abstractmethod
    def get_entries(
            self,
            entry_ids: List[int] | None = None,
            names: List[str] | None = None
    ) -> AsyncGenerator[GermplasmStored, None]:
        """
        Retrieve germplasm entries with optional filtering by name.
        """
        ...

    # Validation query methods
    @abstractmethod
    async def name_in_use(
        self,
        name: str,
        exclude_id: int | None = None
    ) -> bool:
        """Return a boolean whether the name is in use for germplasm entries."""
        pass

    async def entry_exists(self, entry_id: int) -> bool:
        """Check if a germplasm entry exists."""
        entries_exist = await self.entries_exists(entry_ids=[entry_id])
        return entries_exist.get(entry_id, False)

    @abstractmethod
    async def entries_exist(self, entry_ids: List[int]) -> Dict[int, bool]:
        """Batch check if germplasm entries exist."""
        raise NotImplementedError

    async def create_relationship(self, relationship: GermplasmRelationship) -> None:
        await self.create_relationships([relationship])

    # Relationship operations
    @abstractmethod
    async def create_relationships(
        self,
        relationships: List[GermplasmRelationship]
    ) -> None:
        """
        Create a source relationship between germplasm entries.
        source_id, target_id, details
        details should include {type: GermplasmSourceType}
        """
        pass

    async def update_relationship(self, relationship: GermplasmRelationship) -> None:
        await self.update_relationships([relationship])

    # Relationship operations
    @abstractmethod
    async def update_relationships(
        self,
        relationships: List[GermplasmRelationship]
    ) -> None:
        """
        Update a source relationship between germplasm entries.
        """
        pass

    async def delete_relationship(self, relationship: GermplasmRelationship) -> None:
        await self.delete_relationships([relationship])

    # Relationship operations
    @abstractmethod
    async def delete_relationships(
        self,
        relationships: List[GermplasmRelationship]
    ) -> None:
        """
        Delete a relationship between germplasm entries.
        """
        pass

    @abstractmethod
    def get_relationships(self, entry_id: int) -> AsyncGenerator[GermplasmRelationship, None]:
        """Get all relationships for a germplasm entry."""
        pass

    @abstractmethod
    def get_source_relationships(self, entry_id: int) -> AsyncGenerator[GermplasmRelationship, None]:
        """Get all source relationships for a germplasm entry."""
        pass

    @abstractmethod
    def get_sink_relationships(self, entry_id: int) -> AsyncGenerator[GermplasmRelationship, None]:
        """Get all sink relationships for a germplasm entry."""
        pass

    @abstractmethod
    async def get_ancestor_ids(self, entry_id: int, path_length_limit=None) -> List[int]:
        """
        Get all entries that have this entry as a sink.
        Topologically sorted
        """
        pass

    @abstractmethod
    async def get_descendant_ids(self, entry_id: int, path_length_limit=None) -> List[int]:
        """
        Get ids of all entries that have this entry as a source.
        Topologically sorted
        """
        pass

    @abstractmethod
    async def has_path(
        self,
        source_id: int,
        target_id: int
    ) -> bool:
        """Check if a path exists from source to target, used to check if a relationship would create a circular dependency."""
        pass