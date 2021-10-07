from src.dbtools.service_layer import unit_of_work
from src.dbtools.adapters.neo4j.cypher import queries
from src.dbtools.domain.model.accounts import Team
from typing import TYPE_CHECKING
if TYPE_CHECKING:
    from neo4j import Record
    from collections.abc import AsyncGenerator


async def allowed_email(email: str, uow: unit_of_work.Neo4jUnitOfWork):
    with uow:
        record: "Record" = await uow.neo4j.run(queries['get_email'], email=email).single()
        return True if record else False


async def team(team_id: int, uow: unit_of_work.Neo4jUnitOfWork):
    with uow:
        record: "Record" = await uow.neo4j.run(queries['get_team'], team_id=team_id).single()
        return Team(**record['key'])


async def teams(uow: unit_of_work.Neo4jUnitOfWork):
    with uow:
        records: "AsyncGenerator" = await uow.neo4j.run(queries['get_all_teams']).records()
        return [Team(**record['key']) async for record in records]
