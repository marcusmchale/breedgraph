from abc import ABC, abstractmethod

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
    async def germplasm_has_units(self, germplasm_id: int) -> bool:
        """Check if a germplasm is part of any unit definitions"""
        ...

    @abstractmethod
    async def team_tree_controls_persons(self, team_id: int) -> bool:
        """Check if any team of the team tree rooted at the team currently controls a Person"""
        ...

    @abstractmethod
    async def team_controls_entities(self, team_id: int) -> bool:
        """Check if a team currently controls any entities"""
        ...