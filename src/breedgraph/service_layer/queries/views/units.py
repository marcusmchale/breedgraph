from abc import ABC, abstractmethod
from typing import Iterable, List, Dict

from breedgraph.domain.model.unit_graphs import UnitOutput


class AbstractUnitsView(ABC):
    """
    Read units without loading their unit graphs.

    A unit the user can read is returned in full, with the hidden units between it and its parents and children
    skipped, as the repository's redaction reconnects them. A hidden unit asked for by id is returned as a
    placeholder (id and a REDACTED name), a hidden unit graph root keeping its readable descendants as children, so the
    unit graph stays navigable. Units that do not exist are left out.
    """
    user_id: int | None
    read_teams: List[int]

    async def get_units(self, unit_ids: Iterable[int]) -> Dict[int, UnitOutput]:
        unit_ids = [unit_id for unit_id in dict.fromkeys(unit_ids) if unit_id is not None]
        if not unit_ids:
            return {}
        return await self._get_units(unit_ids)

    async def get_unit_graph_roots(self, location_ids: Iterable[int]) -> List[UnitOutput]:
        """The root units of the unit graphs positioned at these locations that the user can read a unit in"""
        location_ids = [location_id for location_id in dict.fromkeys(location_ids) if location_id is not None]
        if not location_ids:
            return []
        return await self._get_unit_graph_roots(location_ids)

    async def get_unit_names(self, unit_ids: Iterable[int]) -> Dict[int, UnitOutput]:
        """Units as id, name and germplasm only, for crediting records; a placeholder where the user cannot read"""
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
    async def _get_unit_graph_roots(self, location_ids: List[int]) -> List[UnitOutput]:
        ...
