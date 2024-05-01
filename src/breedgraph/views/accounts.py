from src.breedgraph.service_layer import unit_of_work
from src.breedgraph.adapters.neo4j.cypher import queries
from src.breedgraph.domain.model.organisations import TeamOutput
from src.breedgraph.domain.model.accounts import AccountOutput, UserOutput
from src.breedgraph.adapters.repositories.accounts import Neo4jAccountRepository
from src.breedgraph.adapters.repositories.organisations import Neo4jOrganisationRepository

from typing import AsyncGenerator
from neo4j import AsyncResult

import logging

logger= logging.getLogger(__name__)
logger.debug("load teams views")

async def teams(
        uow: unit_of_work.Neo4jUnitOfWork,
        user: int
) -> AsyncGenerator[TeamOutput, None]:
    async with uow:
        result: AsyncResult = await uow.tx.run(queries['get_teams_view'], user=user)
        async for record in result:
            yield TeamOutput(**dict(Neo4jOrganisationRepository.team_record_to_team(record['team'])))

async def users(
        uow: unit_of_work.Neo4jUnitOfWork,
        user: int
) -> AsyncGenerator[UserOutput, None]:
    async with uow:
        result: AsyncResult = await uow.tx.run(queries['get_users_view'], user=user)
        async for record in result:
            user_output: UserOutput = UserOutput(
                id=record['user']['id'],
                name = record['user']['name'],
                fullname=record['user']['fullname'],
                email=record['user']['email']
            )
            yield user_output
