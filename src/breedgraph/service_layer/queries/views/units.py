from abc import ABC, abstractmethod
from typing import Iterable, List, Dict

from breedgraph.domain.model.blocks import UnitOutput


class AbstractUnitsView(ABC):
    """
    Read units without loading their blocks.

    Units the user cannot read are returned redacted (id, parents and children only), as the repositories do,
    so the block structure stays navigable. Units that do not exist are left out.
    """
    user_id: int | None
    read_teams: List[int]

    async def get_units(self, unit_ids: Iterable[int]) -> Dict[int, UnitOutput]:
        unit_ids = [unit_id for unit_id in dict.fromkeys(unit_ids) if unit_id is not None]
        if not unit_ids:
            return {}
        return await self._get_units(unit_ids)

    async def get_block_roots(self, location_ids: Iterable[int]) -> List[UnitOutput]:
        """The root units of the blocks positioned at these locations"""
        location_ids = [location_id for location_id in dict.fromkeys(location_ids) if location_id is not None]
        if not location_ids:
            return []
        return await self._get_block_roots(location_ids)

    async def get_unit_names(self, unit_ids: Iterable[int]) -> Dict[int, UnitOutput]:
        """Units as id, name and germplasm only, for crediting records; the name is REDACTED where the user cannot read"""
        unit_ids = [unit_id for unit_id in dict.fromkeys(unit_ids) if unit_id is not None]
        if not unit_ids:
            return {}
        return await self._get_unit_names(unit_ids)

    async def get_descendants_by_subject(self, unit_ids: Iterable[int]) -> Dict[int | None, List[UnitOutput]]:
        """
        Every readable unit below these units, as id, name and subject, keyed by subject id.
        For selecting all the units of a subject at once; units the user cannot read are left out.
        """
        unit_ids = [unit_id for unit_id in dict.fromkeys(unit_ids) if unit_id is not None]
        if not unit_ids:
            return {}
        return await self._get_descendants_by_subject(unit_ids)

    @abstractmethod
    async def _get_descendants_by_subject(self, unit_ids: List[int]) -> Dict[int | None, List[UnitOutput]]:
        ...

    @abstractmethod
    async def _get_unit_names(self, unit_ids: List[int]) -> Dict[int, UnitOutput]:
        ...

    @abstractmethod
    async def _get_units(self, unit_ids: List[int]) -> Dict[int, UnitOutput]:
        ...

    @abstractmethod
    async def _get_block_roots(self, location_ids: List[int]) -> List[UnitOutput]:
        ...
