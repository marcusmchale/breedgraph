from neo4j import AsyncTransaction, AsyncResult
from typing import AsyncGenerator

from src.breedgraph.domain.model.regions import LocationOutput, LocationStored
from src.breedgraph.service_layer.queries.views import AbstractViewsHolder

from src.breedgraph.adapters.neo4j.cypher import queries

from src.breedgraph.domain.model.accounts import UserOutput
from src.breedgraph.domain.model.controls import Access

from typing import Dict, Set

class Neo4jViewsHolder(AbstractViewsHolder):
    def __init__(self, tx: AsyncTransaction):
        self.tx = tx

    async def check_any_account(self) -> bool:
        result: AsyncResult = await self.tx.run(queries['views']['check_any_account'])
        record = await result.single()
        return record.value()

    async def check_allowed_email(self, email: str) -> bool:
        result: AsyncResult = await self.tx.run(
            queries['views']['check_allowed_email'],
            email_lower=email.casefold()
        )
        record = await result.single()
        return record.value()

    async def access_teams(self, user: int = None) -> Dict[Access, Set[int]]:
        if user is None:
            return {a: set() for a in Access}

        result: AsyncResult = await self.tx.run(queries['views']['get_access_teams'], user=user)
        record = await result.single()
        if record is None:
            raise ValueError("User not found")
        access_teams = {Access(key): set(value) for key, value in record.get('access_teams').items()}
        return access_teams

    async def get_user(self, user: int) -> UserOutput:
        result: AsyncResult = await self.tx.run(queries['views']['get_user'], user_id=user)
        record = await result.single(strict=True)
        return UserOutput(**record['user'])

    async def users_for_admin(self, user: int) -> AsyncGenerator[UserOutput, None]:
        result: AsyncResult = await self.tx.run(queries['views']['get_users'], user_id=user)
        async for record in result:
            user_output: UserOutput = UserOutput(**record['user'])
            yield user_output

    async def get_countries(self) -> AsyncGenerator[LocationStored, None]:
        result: AsyncResult = await self.tx.run(queries['views']['get_countries'])
        async for record in result:
            yield LocationStored(**record['location'])
