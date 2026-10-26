from abc import ABC, abstractmethod

from breedgraph.service_layer.queries.read_models import (
    GermplasmEntryOutput, GermplasmRelationshipOutput
)

from typing import List, AsyncGenerator

class AbstractGermplasmView(ABC):
    """
    Germplasm entries as the user may see them: a crop and the entries connected to it are read as one pedigree, the
    entries the user can read in full, linked to the nearest ones they can read, hidden ones between skipped. A hidden
    crop is a placeholder holding the readable entries below it; other hidden entries are placeholders only when
    asked for by id, and lists leave them out (see docs/read-access.md).
    """
    user_id: int|None
    read_teams: List[int]

    async def get_crops(self) -> List[GermplasmEntryOutput]:
        return await self._get_crops()

    @abstractmethod
    async def _get_crops(self) -> List[GermplasmEntryOutput]:
        ...

    async def get_entries_named(self, names: List[str]) -> List[GermplasmEntryOutput]:
        """The entries the user can read with one of the names, or a synonym, ignoring case and surrounding space"""
        names = list(dict.fromkeys(name.strip() for name in names if name and name.strip()))
        if not names:
            return []
        return await self._get_entries_named(names)

    @abstractmethod
    async def _get_entries_named(self, names: List[str]) -> List[GermplasmEntryOutput]:
        ...

    async def get_entries(self, entry_ids: List[int] | None = None) -> List[GermplasmEntryOutput]:
        return await self._get_entries(entry_ids=entry_ids)

    @abstractmethod
    async def _get_entries(self, entry_ids: List[int] | None = None ) -> List[GermplasmEntryOutput]:
        ...

