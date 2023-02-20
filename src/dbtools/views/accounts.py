from src.dbtools.service_layer import unit_of_work
from src.dbtools.adapters.neo4j.cypher import queries
from src.dbtools.domain.model.accounts import TeamStored

from typing import TYPE_CHECKING
if TYPE_CHECKING:
    from typing import List
    from neo4j import Record, AsyncResult


async def allowed_email(email: str, uow: unit_of_work.Neo4jUnitOfWork) -> bool:
    with uow:
        result: AsyncResult = await uow.tx.run(queries['get_email'], email=email)
        record: Record = await result.single()
        return True if record else False


async def team(team_id: int, uow: unit_of_work.Neo4jUnitOfWork) -> TeamStored:
    with uow:
        result = await uow.tx.run(queries['get_team'], team_id=team_id)
        record: Record = await result.single()
        return TeamStored(**record['key'])


async def teams(uow: unit_of_work.Neo4jUnitOfWork) -> "List[TeamStored]":
    with uow:
        result: AsyncResult = await uow.tx.run(queries['get_all_teams'])
        return [TeamStored(**record['key']) async for record in result]
