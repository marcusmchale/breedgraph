from abc import ABC, abstractmethod
from typing import List

class AbstractDependencyGuards(ABC):
    """
    Guards that check cross-aggregate guards before destructive operations.
    These are read-only queries that span aggregate boundaries.
    """

    @abstractmethod
    async def reference_in_use(self, reference_id: int) -> bool:
        """Check if a reference is cited (REFERENCE_FOR) or used as a licence or copyright, including by earlier ontology versions"""
        ...

    @abstractmethod
    async def study_has_datasets(self, study_id: int) -> bool:
        """Check if a study has associated datasets"""
        ...

    @abstractmethod
    async def grouping_has_records(self, grouping_id: int) -> bool:
        """Check if any record is in a group of a record grouping"""
        ...

    @abstractmethod
    async def germplasm_has_units(self, germplasm_id: int) -> bool:
        """Check if a germplasm is part of any unit definitions"""
        ...

    @abstractmethod
    async def germplasm_from_unit(self, unit_id: int) -> bool:
        """Check if any germplasm entry came from a unit"""
        ...

    @abstractmethod
    async def unit_has_derivatives(self, unit_id: int) -> bool:
        """Check if any unit is derived from a unit"""
        ...

    @abstractmethod
    async def unit_has_records(self, unit_id: int) -> bool:
        """Check if any record is for a unit"""
        ...

    @abstractmethod
    async def derivation_cycle(self, unit_id: int, source_ids: List[int]) -> bool:
        """Check if any of the units source_ids is derived from a unit, directly or through others"""
        ...

    @abstractmethod
    async def team_controls_entities(self, team_id: int) -> bool:
        """Check if a team currently controls any entities"""
        ...