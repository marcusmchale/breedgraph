from neo4j import AsyncTransaction, AsyncResult
from typing import AsyncGenerator

from src.breedgraph.service_layer.queries.views.accounts import AbstractAccountsViews
from src.breedgraph.domain.model.accounts import UserOutput

from src.breedgraph.adapters.neo4j.cypher import queries

from typing import List

class Neo4jAccountsViews(AbstractAccountsViews):
    def __init__(self, tx: AsyncTransaction):
        self.tx = tx

    async def check_any_account(self) -> bool:
        result: AsyncResult = await self.tx.run(queries['accounts']['check_any_account'])
        record = await result.single()
        return record.value()

    async def check_allowed_email(self, email: str) -> bool:
        result: AsyncResult = await self.tx.run(
            queries['accounts']['check_allowed_email'],
            email_lower=email.casefold()
        )
        record = await result.single()
        return record.value()

    async def get_user(self, user_id: int) -> UserOutput:
        result: AsyncResult = await self.tx.run(queries['accounts']['get_user'], user_id=user_id)
        record = await result.single(strict=True)
        return UserOutput(**record['user'])

    async def get_users_for_admin(self, team_ids: List[int], user_ids: List[int]) -> AsyncGenerator[UserOutput, None]:
        result: AsyncResult = await self.tx.run(queries['accounts']['get_users_for_admin'], team_ids=team_ids, user_ids=user_ids)
        async for record in result:
            user_output: UserOutput = UserOutput(**record['user'])
            yield user_output

    async def get_users_with_ontology_role_requests(self) -> AsyncGenerator[UserOutput, None]:
        # return all users within outstanding requests for ontology roles
        result: AsyncResult = await self.tx.run(queries['accounts']['get_users_with_ontology_role_requests'])
        async for record in result:
            user_output: UserOutput = UserOutput(**record['user'])
            yield user_output

    async def get_editors_for_ontology_admin(self) -> AsyncGenerator[UserOutput, None]:
        # return all editors for the ontology
        result: AsyncResult = await self.tx.run(queries['accounts']['get_editors_for_ontology_admin'])
        async for record in result:
            user_output: UserOutput = UserOutput(**record['user'])
            yield user_output

    async def get_admins_for_ontology_admin(self) -> AsyncGenerator[UserOutput, None]:
        # return all editors for the ontology
        result: AsyncResult = await self.tx.run(queries['accounts']['get_admins_for_ontology_admin'])
        async for record in result:

            user_output: UserOutput = UserOutput(**record['user'])
            yield user_output