from neo4j import AsyncSession, AsyncResult
from typing import AsyncGenerator

from src.breedgraph.adapters.neo4j.cypher import queries
from src.breedgraph.domain.model.accounts import UserOutput
from src.breedgraph.domain.model.controls import Access
from .base import AbstractViewsHolder


class Neo4jViewsHolder(AbstractViewsHolder):
    def __init__(self, session: AsyncSession):
        self.session = session

    async def check_any_account(self) -> bool:
        result: AsyncResult = await self.session.run(queries['views']['check_any_account'])
        record = await result.single()
        return record.value()

    async def check_allowed_email(self, email: str) -> bool:
        result: AsyncResult = await self.session.run(
            queries['views']['check_allowed_email'],
            email_lower=email.casefold()
        )
        record = await result.single()
        return record.value()

    async def access_teams(self, user: int) -> dict[Access, list[int]]:
        result: AsyncResult = await self.session.run(queries['views']['get_access_teams'], user=user)
        record = await result.single()
        if record is None:
            raise ValueError("User not found")
        return record.get('access_teams')

    async def users(self, user: int) -> AsyncGenerator[UserOutput, None]:
        result: AsyncResult = await self.session.run(queries['views']['get_users'], user=user)
        async for record in result:
            user_output: UserOutput = UserOutput(
                id=record['user']['id'],
                name=record['user']['name'],
                fullname=record['user']['fullname'],
                email=record['user']['email']
            )
            yield user_output