from src.breedgraph.service_layer import unit_of_work
from src.breedgraph.adapters.neo4j.cypher import queries
from src.breedgraph.domain.model.organisations import TeamOutput
from src.breedgraph.domain.model.organisations import Organisation
from src.breedgraph.domain.model.accounts import AccountOutput, UserOutput
from src.breedgraph.adapters.repositories.accounts import Neo4jAccountRepository
from src.breedgraph.adapters.repositories.organisations import Neo4jOrganisationsRepository

from typing import AsyncGenerator
from neo4j import AsyncResult

import logging

logger= logging.getLogger(__name__)
logger.debug("load teams views")

async def teams(
        uow: unit_of_work.AbstractUnitOfWork,
        user: int
) -> AsyncGenerator[TeamOutput, None]:
    async with uow.get_repositories() as uow:
        result: AsyncResult = await uow.tx.run(queries['views']['get_teams'], user=user)
        async for record in result:
            yield TeamOutput(**dict(Neo4jOrganisationsRepository.team_record_to_team(record['team'])))

async def users(
        uow: unit_of_work.Neo4jUnitOfWork,
        user: int
) -> AsyncGenerator[UserOutput, None]:
    async with uow.get_repositories() as uow:
        result: AsyncResult = await uow.tx.run(queries['views']['get_users'], user=user)
        async for record in result:
            user_output: UserOutput = UserOutput(
                id=record['user']['id'],
                name = record['user']['name'],
                fullname=record['user']['fullname'],
                email=record['user']['email']
            )
            yield user_output
