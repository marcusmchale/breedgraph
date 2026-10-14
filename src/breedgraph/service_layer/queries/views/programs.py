from abc import ABC, abstractmethod

from breedgraph.domain.model.programs import StudyStored

from typing import List


class AbstractProgramsView(ABC):
    user_id: int | None
    read_teams: List[int]

    async def get_study(self, study_id: int) -> StudyStored | None:
        """
        One study without loading its program, as the programs repository gives it: redacted when a registered
        user cannot read it, and None when it does not exist or an anonymous user cannot read it.
        """
        return await self._get_study(study_id=study_id)

    @abstractmethod
    async def _get_study(self, study_id: int) -> StudyStored | None:
        ...
