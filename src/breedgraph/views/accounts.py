from src.breedgraph.service_layer import unit_of_work
from src.breedgraph.adapters.neo4j.cypher import queries
from src.breedgraph.domain.model.organisations import TeamOutput
from src.breedgraph.domain.model.organisations import Organisation
from src.breedgraph.domain.model.accounts import AccountOutput, UserOutput
from src.breedgraph.adapters.repositories.accounts import Neo4jAccountRepository
from src.breedgraph.adapters.repositories.organisations import Neo4jOrganisationsRepository
from src.breedgraph.domain.model.controls import Access

from typing import AsyncGenerator
from neo4j import AsyncResult, AsyncSession, AsyncTransaction

import logging

logger= logging.getLogger(__name__)
logger.debug("load teams views")

async def access_teams(uow: unit_of_work.Neo4jUnitOfWork, user: int) -> dict[Access, list[int]]:
    session: AsyncSession = uow.driver.session()
    result: AsyncResult = await session.run(queries['views']['get_access_teams'], user=user)
    record = await result.single()
    return record.get('access_teams')

async def users(
        uow: unit_of_work.Neo4jUnitOfWork,
        user: int
) -> AsyncGenerator[UserOutput, None]:
    session: AsyncSession = uow.driver.session()
    result: AsyncResult = await session.run(queries['views']['get_users'], user=user)
    async for record in result:
        user_output: UserOutput = UserOutput(
            id=record['user']['id'],
            name = record['user']['name'],
            fullname=record['user']['fullname'],
            email=record['user']['email']
        )
        yield user_output
    await session.close()