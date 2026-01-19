from neo4j import AsyncTransaction

from src.breedgraph.service_layer.application.extra_aggregate import AbstractExtraAggregateService

from src.breedgraph.adapters.neo4j.cypher.query_builders.extra import delete_relationship
from src.breedgraph.adapters.neo4j.cypher import queries

import logging

logger = logging.getLogger(__name__)


class Neo4jExtraAggregateService(AbstractExtraAggregateService):

    def __init__(self, tx: AsyncTransaction):
        self.tx = tx

    async def _delete_relationship(self, source_id, source_label, sink_id, sink_label, relationship_label) -> None:
        query = delete_relationship(source_label, sink_label, relationship_label)
        await self.tx.run(query, source_id=source_id, sink_id=sink_id)

    async def _reference_in_use(self, reference_id) -> bool:
        query = queries.get('reference_in_use')
        result = await self.tx.run(query, reference_id=reference_id)
        record = await result.single()
        return record.get('in_use')

