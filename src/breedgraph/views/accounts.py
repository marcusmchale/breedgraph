from src.breedgraph.service_layer import unit_of_work
from src.breedgraph.adapters.neo4j.cypher import queries
from src.breedgraph.domain.model.accounts import TeamStored, Email
from src.breedgraph.custom_exceptions import NoResultFoundError

from typing import List, Optional, Generator
from neo4j import Record, AsyncResult


import logging

logger= logging.getLogger(__name__)
logger.debug("load accounts views")


async def team(
        uow: unit_of_work.Neo4jUnitOfWork,
        team_name: Optional[str] = None,
        team_id: Optional[int] = None,
        parent_id: Optional[int] = None
) -> TeamStored:
    async with uow:
        if team_id:
            result = await uow.tx.run(queries['get_team'], team_id=team_id)
        elif team_name and parent_id:
            result = await uow.tx.run(queries['get_team_with_parent_by_name'], name_lower=team_name.casefold(), parent_id=parent_id)
        elif team_name and not parent_id:
            result = await uow.tx.run(queries['get_team_without_parent_by_name'], name_lower=team_name.casefold())
        else:
            raise ValueError("Must provide either a name or ID for team search")

        record: Record = await result.single()
        if record is None:
            raise NoResultFoundError
        return TeamStored(**record)

async def teams(uow: unit_of_work.Neo4jUnitOfWork) -> Generator[TeamStored, None, None]:
    async with uow:
        result: AsyncResult = await uow.tx.run(queries['get_all_teams'])
        records = [record async for record in result]
        for record in records:
            yield TeamStored(**record)
