from neo4j import AsyncSession

from breedgraph.adapters.neo4j.cypher.query_builders import people as people_queries
from breedgraph.adapters.neo4j.cypher.matching import exact_text_regex
from breedgraph.domain.model.controls import ReadRelease
from breedgraph.domain.model.people import PersonOutput, PersonView
from breedgraph.domain.model.time_descriptors import deserialize_time
from breedgraph.service_layer.queries.views.people import AbstractPeopleView

from typing import Dict, List


class Neo4jPeopleView(AbstractPeopleView):
    """
    The read checks and views are in the Cypher (see query_builders.people). Records parse straight into PersonOutput,
    not through the repository's parser, so fields outside the view stay None
    """

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
        person = dict(record['person'])
        return PersonOutput(
            id=person['id'],
            name=person.get('name'),
            institution=person.get('institution'),
            teams=list(person.get('teams') or []),
            informed_attestation=person.get('informed_attestation'),
            orcid=person.get('orcid'),
            user=person.get('user'),
            claims=list(person.get('claims') or []),
            recorded_by=person.get('recorded_by'),
            recorded_at=deserialize_time(person.get('recorded_at')),
            erased_at=deserialize_time(person.get('erased_at')),
            view=PersonView(person['view']),
            erased=person['erased'],
            linked=person.get('linked')
        )

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
            name_regex=exact_text_regex(name) if name else None
        )
