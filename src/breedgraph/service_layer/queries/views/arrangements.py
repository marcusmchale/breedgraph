from abc import ABC, abstractmethod

from breedgraph.domain.model.arrangements import LayoutOutput

from typing import List, Dict, Iterable


class AbstractArrangementsView(ABC):
    """
    Layouts as the user may see them (see query_builders.arrangements): readable layouts in full, with hidden ones
    skipped in their arrangement's tree, and placeholders only for hidden layouts asked for directly or arrangement
    roots holding readable layouts.
    """
    user_id: int | None
    read_teams: List[int]

    async def get_arrangements(self, location_id: int) -> List[LayoutOutput]:
        """The root of every arrangement at this location that the user can read a layout in"""
        return await self._get_arrangements(location_id)

    @abstractmethod
    async def _get_arrangements(self, location_id: int) -> List[LayoutOutput]:
        ...

    async def get_layouts(self, layout_ids: Iterable[int]) -> Dict[int, LayoutOutput]:
        """The layouts with these ids that exist, keyed by id, as placeholders where the user cannot read them"""
        layout_ids = [layout_id for layout_id in dict.fromkeys(layout_ids) if layout_id is not None]
        if not layout_ids:
            return {}
        return await self._get_layouts(layout_ids)

    @abstractmethod
    async def _get_layouts(self, layout_ids: List[int]) -> Dict[int, LayoutOutput]:
        ...
