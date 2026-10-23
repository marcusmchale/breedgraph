from typing import List

from neo4j import AsyncSession, AsyncResult

from breedgraph.domain.model.controls import ReadRelease
from breedgraph.domain.model.time_descriptors import deserialize_time
from breedgraph.adapters.neo4j.cypher.query_builders import germplasm as germplasm_queries
from breedgraph.service_layer.queries.read_models.germplasm import (
    GermplasmEntryOutput,
    GermplasmRelationshipOutput,
    GermplasmSourceType
)

from breedgraph.service_layer.queries.views import AbstractGermplasmView

import logging
logger = logging.getLogger(__name__)

class Neo4jGermplasmView(AbstractGermplasmView):
    """The read checks and placeholders are in the Cypher (see query_builders.germplasm)"""

    def __init__(self, session: AsyncSession, user_id: int|None, read_teams: List[int]):
        self.session = session
        self.user_id = user_id
        self.read_teams = read_teams

    @staticmethod
    def record_to_output(record) -> GermplasmEntryOutput:
        entry = record["entry"]
        entry.pop("name_lower", None)
        entry.pop('authors', None)  # no longer stored, may remain on older entries
        # a time is stored with its unit and step, the precision it was given at
        entry['time'] = deserialize_time(entry.get('time'), unit=entry.pop('time_unit', None), step=entry.pop('time_step', None))
        entry['sources'] = [GermplasmRelationshipOutput(**rel) for rel in entry.get('sources', [])]
        entry['sinks'] = [GermplasmRelationshipOutput(**rel) for rel in entry.get('sinks', [])]
        return GermplasmEntryOutput(**entry)

    async def _run(self, query: str, **params) -> List[GermplasmEntryOutput]:
        result: AsyncResult = await self.session.run(
            query,
            **params,
            read_teams=self.read_teams,
            minimum_release=int(ReadRelease.PUBLIC if self.user_id is None else ReadRelease.REGISTERED)
        )
        return [self.record_to_output(record) async for record in result]

    async def _get_crops(self) -> List[GermplasmEntryOutput]:
        return await self._run(germplasm_queries.read_crops())

    async def _get_entries(self, entry_ids: List[int] | None = None) -> List[GermplasmEntryOutput]:
        if entry_ids:
            return await self._run(germplasm_queries.read_entries(), entry_ids=entry_ids)
        return await self._run(germplasm_queries.read_all_entries())
