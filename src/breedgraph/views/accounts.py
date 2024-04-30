from src.breedgraph.service_layer import unit_of_work
from src.breedgraph.adapters.neo4j.cypher import queries
from src.breedgraph.domain.model.organisations import TeamStored, TeamOutput
from src.breedgraph.domain.model.accounts import AccountOutput, UserOutput, Affiliation, Access, Authorisation
from src.breedgraph.adapters.repositories.accounts import Neo4jAccountRepository
from src.breedgraph.adapters.repositories.organisations import Neo4jOrganisationRepository


from src.breedgraph.custom_exceptions import (
    NoResultFoundError,
    UnauthorisedOperationError
)

from typing import List, Optional, Generator, AsyncGenerator
from neo4j import Record, AsyncResult


import logging

logger= logging.getLogger(__name__)
logger.debug("load teams views")


async def teams(
        uow: unit_of_work.Neo4jUnitOfWork,
        user: int
) -> AsyncGenerator[TeamOutput, None]:
    async with uow:
        result: AsyncResult = await uow.tx.run(queries['get_teams_user'], user=user)
        async for record in result:
            yield TeamOutput(**dict(Neo4jOrganisationRepository.team_record_to_team(record['team'])))

async def accounts(
        uow: unit_of_work.Neo4jUnitOfWork,
        user: int
) -> AsyncGenerator[AccountOutput, None]:
    async with uow:
        result: AsyncResult = await uow.tx.run(queries['get_accounts_for_admin'], user=user)
        async for record in result:
            user_output: UserOutput = UserOutput(
                id=record['user']['id'],
                fullname=record['user']['fullname'],
                email=record['user']['email']
            )
            affiliations = [Neo4jAccountRepository.affiliation_record_to_affiliation(a) for a in record['affiliations']]
            yield AccountOutput(user=user_output, affiliations=affiliations)

#async def affiliations(
#        uow: unit_of_work.Neo4jUnitOfWork,
#        user_id: int,
#        access: Optional[Access] = None,
#        authorisation: Optional[Authorisation] = None
#) -> AsyncGenerator[Affiliation, None]:
#    async with uow:
#        if authorisation is Authorisation.REQUESTED:
#            result: AsyncResult = await uow.tx.run(queries['get_affiliation_requests'], user_id=user_id)
#        else:
#            result: AsyncResult = await uow.tx.run(queries['get_affiliations'], user_id=user_id)
#        async for record in result:
#            if all([
#                access is None or record['access'] == access.name,
#                authorisation is None or record['authorisation'] == authorisation.name
#            ]):
#                yield Affiliation(
#                    team_id = record['team_id'],
#                    access=Access[record['access']] if record['access'] else Access.NONE,
#                    authorisation=Authorisation[record['authorisation']] if record['authorisation'] else Authorisation.NONE,
#                )
#
#
#
#

