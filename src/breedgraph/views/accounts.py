from src.breedgraph.service_layer import unit_of_work
from src.breedgraph.adapters.neo4j.cypher import queries
from src.breedgraph.domain.model.accounts import TeamStored
from src.breedgraph.custom_exceptions import (
    NoResultFoundError,
    UnauthorisedOperationError
)

from typing import List, Optional, Generator, AsyncGenerator
from neo4j import Record, AsyncResult


import logging

logger= logging.getLogger(__name__)
logger.debug("load accounts views")


async def teams(
        uow: unit_of_work.Neo4jUnitOfWork,
        user_id: Optional[int] = None,
        team_id: Optional[int] = None,
        team_name: Optional[str] = None,
        parent_id: Optional[int] = None
) -> AsyncGenerator[TeamStored, None]:
    async with uow:
        if all([
            i is None for i in [user_id, team_id, team_name, parent_id]
        ]):
            result: AsyncResult = await uow.tx.run(queries['get_teams_all'])

        elif user_id is not None:
            if any([i is not None for i in [team_id, team_name, parent_id]]):
                raise NotImplementedError("User_id filtering combined with specific team query is not implemented")

            result: AsyncResult = await uow.tx.run(queries['get_teams_user'], user_id=user_id)

        elif team_id is not None:
            result: AsyncResult = await uow.tx.run(queries['get_team'], team_id=team_id)

        elif team_name is not None:
            if parent_id is None:
                result: AsyncResult = await uow.tx.run(
                    queries['get_team_without_parent_by_name'],
                    name_lower=team_name.casefold()
                )
            else:
                result: AsyncResult = await uow.tx.run(
                    queries['get_team_with_parent_by_name'],
                    name_lower=team_name.casefold(),
                    parent_id=parent_id
                )
        async for record in result:
            yield TeamStored(**record)



