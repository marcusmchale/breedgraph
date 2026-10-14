from neo4j import AsyncSession

from breedgraph.adapters.neo4j.cypher.query_builders import programs as program_queries
from breedgraph.adapters.neo4j.repositories.programs import Neo4jProgramsRepository
from breedgraph.domain.model.controls import ReadRelease
from breedgraph.domain.model.programs import ProgramStored, TrialStored, StudyStored
from breedgraph.service_layer.queries.views.programs import AbstractProgramsView

from typing import List


class Neo4jProgramsView(AbstractProgramsView):
    """The read checks and redaction are in the Cypher (see query_builders.programs); records parse as the repository's"""

    def __init__(self, session: AsyncSession, user_id: int | None, read_teams: List[int]):
        self.session = session
        self.user_id = user_id
        self.read_teams = read_teams

    async def _run(self, query: str, **params):
        return await self.session.run(
            query,
            **params,
            read_teams=self.read_teams,
            minimum_release=ReadRelease.PUBLIC if self.user_id is None else ReadRelease.REGISTERED
        )

    async def _get_programs(self) -> List[ProgramStored]:
        result = await self._run(program_queries.read_programs())
        return [Neo4jProgramsRepository.record_to_program(dict(record['program'])) async for record in result]

    async def _get_program(
            self,
            program_id: int | None = None,
            trial_id: int | None = None,
            study_id: int | None = None
    ) -> ProgramStored | None:
        if program_id is not None:
            result = await self._run(program_queries.read_program('program'), program_id=program_id)
        elif trial_id is not None:
            result = await self._run(program_queries.read_program('trial'), trial_id=trial_id)
        else:
            result = await self._run(program_queries.read_program('study'), study_id=study_id)
        record = await result.single()
        return Neo4jProgramsRepository.record_to_program(dict(record['program'])) if record else None

    async def _get_trial(self, trial_id: int | None = None, study_id: int | None = None) -> TrialStored | None:
        if trial_id is not None:
            result = await self._run(program_queries.read_trial('trial'), trial_id=trial_id)
        else:
            result = await self._run(program_queries.read_trial('study'), study_id=study_id)
        record = await result.single()
        return Neo4jProgramsRepository.record_to_trial(dict(record['trial'])) if record else None

    async def _get_study(self, study_id: int) -> StudyStored | None:
        result = await self._run(program_queries.read_study(), study_id=study_id)
        record = await result.single()
        return Neo4jProgramsRepository.record_to_study(dict(record['study'])) if record else None
