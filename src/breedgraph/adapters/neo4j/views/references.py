from neo4j import AsyncSession

from breedgraph.adapters.neo4j.cypher.query_builders import references as reference_queries
from breedgraph.adapters.neo4j.repositories.references import Neo4jReferencesRepository
from breedgraph.domain.model.controls import ReadRelease
from breedgraph.domain.model.references import ReferenceStoredBase, ReferenceType
from breedgraph.service_layer.queries.views.references import AbstractReferencesView

from typing import List


class Neo4jReferencesView(AbstractReferencesView):
    """The read checks and placeholders are in the Cypher (see query_builders.references); records parse as the repository's"""

    def __init__(self, session: AsyncSession, user_id: int | None, read_teams: List[int]):
        self.session = session
        self.user_id = user_id
        self.read_teams = read_teams

    async def _run(self, query: str, **params) -> List[ReferenceStoredBase]:
        result = await self.session.run(
            query,
            **params,
            read_teams=self.read_teams,
            minimum_release=int(ReadRelease.PUBLIC if self.user_id is None else ReadRelease.REGISTERED)
        )
        return [Neo4jReferencesRepository.record_to_reference(dict(record['reference'])) async for record in result]

    async def _get_references(self, reference_ids: List[int]) -> List[ReferenceStoredBase]:
        return await self._run(reference_queries.read_references(), reference_ids=reference_ids)

    async def _get_file_reference(self, file_id: str) -> ReferenceStoredBase | None:
        references = await self._run(reference_queries.read_file_reference(), file_id=file_id)
        return references[0] if references else None

    async def _search_references(
            self,
            description: str,
            reference_types: List[ReferenceType] | None
    ) -> List[ReferenceStoredBase]:
        return await self._run(
            reference_queries.search_references(),
            description=description,
            types=[reference_type.value for reference_type in reference_types] if reference_types else None
        )
