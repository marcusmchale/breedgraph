from abc import ABC, abstractmethod

from breedgraph.domain.model.programs import ProgramStored, TrialStored, StudyStored

from typing import List


class AbstractProgramsView(ABC):
    """
    Programs, trials and studies as the user may see them. What the user can read is returned in full; what they
    cannot is returned as a placeholder, its id and a REDACTED name, only when it was asked for directly or when it
    holds members they can read, and is otherwise left out.
    """
    user_id: int | None
    read_teams: List[int]

    async def get_programs(self) -> List[ProgramStored]:
        """Every program the user can read, or that holds trials or studies they can read"""
        return await self._get_programs()

    @abstractmethod
    async def _get_programs(self) -> List[ProgramStored]:
        ...

    async def get_program(
            self,
            program_id: int | None = None,
            trial_id: int | None = None,
            study_id: int | None = None
    ) -> ProgramStored | None:
        """A program by its id, or a trial's or study's; None when it does not exist"""
        if program_id is None and trial_id is None and study_id is None:
            raise ValueError("Program, Trial or Study ID required to fetch a program")
        return await self._get_program(program_id=program_id, trial_id=trial_id, study_id=study_id)

    @abstractmethod
    async def _get_program(
            self,
            program_id: int | None = None,
            trial_id: int | None = None,
            study_id: int | None = None
    ) -> ProgramStored | None:
        ...

    async def get_trial(self, trial_id: int | None = None, study_id: int | None = None) -> TrialStored | None:
        """A trial by its id or a study's; None when it does not exist"""
        if trial_id is None and study_id is None:
            raise ValueError("Trial or Study ID required to fetch a trial")
        return await self._get_trial(trial_id=trial_id, study_id=study_id)

    @abstractmethod
    async def _get_trial(self, trial_id: int | None = None, study_id: int | None = None) -> TrialStored | None:
        ...

    async def get_study(self, study_id: int) -> StudyStored | None:
        """A study by its id; None when it does not exist"""
        return await self._get_study(study_id=study_id)

    @abstractmethod
    async def _get_study(self, study_id: int) -> StudyStored | None:
        ...
