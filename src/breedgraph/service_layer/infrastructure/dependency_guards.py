from abc import ABC, abstractmethod

class AbstractDependencyGuards(ABC):
    """
    Guards that check cross-aggregate dependencies before destructive operations.
    These are read-only queries that span aggregate boundaries.
    """

    @abstractmethod
    async def reference_in_use(self, reference_id: int) -> bool:
        """Check if a reference is being used by any records"""
        ...

    @abstractmethod
    async def study_has_datasets(self, study_id: int) -> bool:
        """Check if a study has associated datasets"""
        ...
