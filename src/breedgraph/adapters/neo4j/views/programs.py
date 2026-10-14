from neo4j import AsyncSession

from breedgraph.adapters.neo4j.cypher import queries
from breedgraph.adapters.neo4j.repositories.programs import Neo4jProgramsRepository
from breedgraph.domain.model.controls import ReadRelease
from breedgraph.domain.model.programs import StudyStored
from breedgraph.service_layer.queries.views.programs import AbstractProgramsView

from typing import List


class Neo4jProgramsView(AbstractProgramsView):

    def __init__(self, session: AsyncSession, user_id: int | None, read_teams: List[int]):
        self.session = session
        self.user_id = user_id
        self.read_teams = read_teams

    async def _get_study(self, study_id: int) -> StudyStored | None:
        result = await self.session.run(
            queries['programs']['read_study_for_read_teams'],
            study_id=study_id,
            read_teams=self.read_teams,
            minimum_release=ReadRelease.PUBLIC if self.user_id is None else ReadRelease.REGISTERED
        )
        record = await result.single()
        if record is None:
            return None
        if not record['readable'] and self.user_id is None:
            return None
        study = Neo4jProgramsRepository.record_to_study(record['study'])
        return study if record['readable'] else study.without_details()
