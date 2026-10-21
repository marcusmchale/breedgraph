from abc import ABC, abstractmethod
from typing import Dict, List, Set

from numpy import datetime64

from breedgraph.domain.services.unit_positions import UnitPositions, PositionWrites


class UnitPositionsPersistenceService(ABC):
    """
    Reads and writes units' positions outside the unit graph aggregate (application.unit_positions): the units' write
    locks are taken as their positions are read, and the writes find the positions read by their keys
    """

    @abstractmethod
    async def read_positions_locked(self, unit_ids: List[int]) -> Dict[int, UnitPositions]:
        """The units with their own positions, once their write locks are taken; units not found are left out"""
        ...

    @abstractmethod
    async def write(self, writes: PositionWrites) -> None:
        ...

    @abstractmethod
    async def arrival_unit_ids(
            self,
            location_id: int,
            start: datetime64 | None,
            unit_id: int | None,
            read_teams: Set[int],
            minimum_release: int
    ) -> List[int]:
        """The units of an arrival that the user can read, as unitsArrivalUnits lists them"""
        ...
