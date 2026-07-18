from neo4j import AsyncTransaction

from breedgraph.service_layer.application.aggregate_restructuring import AbstractAggregateRestructuringService

from breedgraph.adapters.neo4j.cypher.query_builders.restructuring import delete_relationship

import logging

logger = logging.getLogger(__name__)


class Neo4jAggregateRestructuringService(AbstractAggregateRestructuringService):

    def __init__(self, tx: AsyncTransaction):
        self.tx = tx

    async def _delete_relationship(self, source_id, source_label, sink_id, sink_label, relationship_label) -> None:
        query = delete_relationship(source_label, sink_label, relationship_label)
        await self.tx.run(query, source_id=source_id, sink_id=sink_id)
