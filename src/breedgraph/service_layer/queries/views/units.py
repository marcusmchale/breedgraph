from abc import ABC, abstractmethod
from typing import Iterable, List, Dict, Tuple

from numpy import datetime64

from breedgraph.domain.model.unit_graphs import UnitOutput, UnitArrival


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

    async def get_ancestor_ids(self, unit_ids: Iterable[int]) -> Dict[int, List[int]]:
        """
        The ids of the units above each readable unit that the user can read, closest first, with its unit graph's
        root even when hidden; a hidden unit has none, as its parents are not shown
        """
        unit_ids = [unit_id for unit_id in dict.fromkeys(unit_ids) if unit_id is not None]
        if not unit_ids:
            return {}
        found = await self._get_ancestor_ids(unit_ids)
        return {unit_id: found.get(unit_id, []) for unit_id in unit_ids}

    async def get_arrivals(self, location_ids: Iterable[int], unit_id: int | None = None) -> List[UnitArrival]:
        """
        The arrivals at these locations: the readable units, not unit graph roots, with a position at one of them whose
        parents were not there at its start, by location and start; newest first, undated last. With unit_id, only the
        units at, below or above it. A search: nothing at a location the user cannot read (docs/read-access.md, rule 5)
        """
        location_ids = [location_id for location_id in dict.fromkeys(location_ids) if location_id is not None]
        if not location_ids:
            return []
        return await self._get_arrivals(location_ids, unit_id)

    async def get_arrival_units(
            self, location_id: int, start: datetime64 | None, unit_id: int | None = None, offset: int = 0, limit: int = 100
    ) -> List[UnitOutput]:
        """A page of the units of the arrival at a location from a start as entered, by name; see get_arrivals"""
        return await self._get_arrival_units(location_id, start, unit_id, max(offset, 0), max(limit, 0))

    async def get_arrival_units_by_subject(
            self, arrivals: Iterable[Tuple[int, datetime64 | None]]
    ) -> Dict[Tuple[int, str | None], Dict[int | None, List[UnitOutput]]]:
        """
        The units of each arrival (location id, start), as id, name and subject, by subject id, for selecting them all at
        once; keyed by the location id and the start as text, as entered
        """
        arrivals = list(arrivals)
        if not arrivals:
            return {}
        return await self._get_arrival_units_by_subject(arrivals)

    async def get_arrival_unit_ids(self, location_id: int, start: datetime64 | None, unit_id: int | None = None) -> List[int]:
        """The ids of the units of an arrival, all of them, as get_arrival_units finds them"""
        return await self._get_arrival_unit_ids(location_id, start, unit_id)

    @abstractmethod
    async def _get_arrivals(self, location_ids: List[int], unit_id: int | None) -> List[UnitArrival]:
        ...

    @abstractmethod
    async def _get_arrival_units(
            self, location_id: int, start: datetime64 | None, unit_id: int | None, offset: int, limit: int
    ) -> List[UnitOutput]:
        ...

    @abstractmethod
    async def _get_arrival_units_by_subject(
            self, arrivals: List[Tuple[int, datetime64 | None]]
    ) -> Dict[Tuple[int, str | None], Dict[int | None, List[UnitOutput]]]:
        ...

    @abstractmethod
    async def _get_arrival_unit_ids(self, location_id: int, start: datetime64 | None, unit_id: int | None) -> List[int]:
        ...

    @abstractmethod
    async def _get_ancestor_ids(self, unit_ids: List[int]) -> Dict[int, List[int]]:
        ...

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
