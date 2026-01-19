from neo4j import AsyncTransaction, AsyncResult

from src.breedgraph.service_layer.infrastructure.constraints import AbstractConstraintsHandler
from src.breedgraph.adapters.neo4j.cypher import queries
from src.breedgraph.domain.model.accounts import OntologyRole

class Neo4jConstraintsHandler(AbstractConstraintsHandler):
    def __init__(self, tx: AsyncTransaction, user_id: int = None):
        self.tx = tx
        self.user_id = user_id

    async def accounts_exist(self) -> bool:
        result: AsyncResult = await self.tx.run(queries['accounts']['check_any_account'])
        record = await result.single()
        return record.value()

    async def email_allowed(self, email: str) -> bool:
        result: AsyncResult = await self.tx.run(
            queries['accounts']['check_allowed_email'],
            email_lower=email.casefold()
        )
        record = await result.single()
        return record.value()

    async def is_ontology_admin(self) -> bool:
        result: AsyncResult = await self.tx.run(
            queries['accounts']['get_user_ontology_role'],
            user_id=self.user_id
        )
        record = await result.single()
        role = OntologyRole(record.value())
        return role == OntologyRole.ADMIN

    async def is_last_ontology_admin(self) -> bool:
        result: AsyncResult = await self.tx.run(
            queries['constraints']['is_last_ontology_admin'],
            user_id=self.user_id
        )
        record = await result.single()
        return record.value()