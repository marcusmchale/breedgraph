from typing import List

from neo4j import AsyncSession, AsyncResult, Record, AsyncTransaction
from neo4j.exceptions import ResultNotSingleError
from collections import defaultdict
from dataclasses import fields

from breedgraph.domain.model.controls import ReadRelease
from breedgraph.adapters.neo4j.cypher import queries
from breedgraph.service_layer.queries.read_models.germplasm import (
    GermplasmEntryOutput,
    GermplasmRelationshipOutput,
    GermplasmSourceType
)

from breedgraph.service_layer.queries.views import AbstractGermplasmView

import logging
logger = logging.getLogger(__name__)

class Neo4jGermplasmView(AbstractGermplasmView):

    def __init__(self, session: AsyncSession, user_id: int|None, read_teams: List[int]):
        self.session = session
        self.user_id = user_id
        self.read_teams = read_teams

    @staticmethod
    def record_to_output(record) -> GermplasmEntryOutput:
        entry = record["entry"]
        entry.pop("name_lower", None)
        entry['sources'] = [GermplasmRelationshipOutput(**rel) for rel in entry.get('sources', [])]
        entry['sinks'] = [GermplasmRelationshipOutput(**rel) for rel in entry.get('sinks', [])]
        return GermplasmEntryOutput(**entry)

    async def _get_crops(self) -> List[GermplasmEntryOutput]:
        async with await self.session.begin_transaction() as tx:
            query = queries['germplasm']['get_output_for_read_teams_crops']
            result: AsyncResult = await tx.run(
                query,
                read_teams = self.read_teams,
                minimum_release = ReadRelease.PUBLIC if self.user_id is None else ReadRelease.REGISTERED
            )
            crops = [self.record_to_output(record) async for record in result]
            return crops

    async def _get_entries(self, entry_ids: List[int] | None = None) -> List[GermplasmEntryOutput]:
        async with await self.session.begin_transaction() as tx:
            if entry_ids:
                query = queries['germplasm']['get_output_for_read_teams_by_id']
                result: AsyncResult = await tx.run(
                    query,
                    entry_ids = entry_ids,
                    read_teams = self.read_teams,
                    minimum_release = ReadRelease.PUBLIC if self.user_id is None else ReadRelease.REGISTERED
                )

            else:
                query = queries['germplasm']['get_output_for_read_teams']
                result: AsyncResult = await tx.run(
                    query,
                    read_teams = self.read_teams,
                    minimum_release = ReadRelease.PUBLIC if self.user_id is None else ReadRelease.REGISTERED
                )
            entries = [self.record_to_output(record) async for record in result]
            return entries

