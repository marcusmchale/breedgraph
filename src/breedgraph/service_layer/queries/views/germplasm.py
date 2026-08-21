from abc import ABC, abstractmethod

from breedgraph.service_layer.queries.read_models import (
    GermplasmEntryOutput, GermplasmRelationshipOutput
)

from typing import List, AsyncGenerator

class AbstractGermplasmView(ABC):
    user_id: int|None
    read_teams: List[int]

    async def get_crops(self) -> List[GermplasmEntryOutput]:
        return await self._get_crops()

    @abstractmethod
    async def _get_crops(self) -> List[GermplasmEntryOutput]:
        ...

    async def get_entries(self, entry_ids: List[int] | None = None) -> List[GermplasmEntryOutput]:
        return await self._get_entries(entry_ids=entry_ids)

    @abstractmethod
    async def _get_entries(self, entry_ids: List[int] | None = None ) -> List[GermplasmEntryOutput]:
        ...

