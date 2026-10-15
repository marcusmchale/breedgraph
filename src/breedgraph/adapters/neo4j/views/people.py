import re

from neo4j import AsyncSession

from breedgraph.adapters.neo4j.cypher.query_builders import people as people_queries
from breedgraph.adapters.neo4j.repositories.people import Neo4jPeopleRepository
from breedgraph.domain.model.controls import ReadRelease
from breedgraph.domain.model.people import PersonOutput
from breedgraph.service_layer.queries.views.people import AbstractPeopleView

from typing import Dict, List


class Neo4jPeopleView(AbstractPeopleView):
    """The read checks and placeholders are in the Cypher (see query_builders.people); records parse as the repository's"""

    def __init__(self, session: AsyncSession, user_id: int | None, read_teams: List[int]):
        self.session = session
        self.user_id = user_id
        self.read_teams = read_teams

    async def _records(self, query: str, **params):
        return await self.session.run(
            query,
            **params,
            user_id=self.user_id,
            read_teams=self.read_teams,
            minimum_release=int(ReadRelease.PUBLIC if self.user_id is None else ReadRelease.REGISTERED)
        )

    @staticmethod
    def _to_output(record) -> PersonOutput:
        return Neo4jPeopleRepository.record_to_person(dict(record['person'])).to_output()

    async def _run(self, query: str, **params) -> List[PersonOutput]:
        return [self._to_output(record) async for record in await self._records(query, **params)]

    async def _get_people_by_users(self, user_ids: List[int]) -> Dict[int, PersonOutput]:
        result = await self._records(people_queries.read_people_by_user(), user_ids=user_ids)
        return {record['user_id']: self._to_output(record) async for record in result}

    async def _get_people(self, person_ids: List[int]) -> List[PersonOutput]:
        return await self._run(people_queries.read_people(), person_ids=person_ids)

    async def _search_people(self, name: str | None) -> List[PersonOutput]:
        return await self._run(
            people_queries.search_people(),
            name_regex=f"(?i)^{re.escape(name)}$" if name else None
        )
