from abc import ABC, abstractmethod

from src.dbtools.domain.model.accounts import Team

from src.dbtools.adapters.repositories.cypher import queries
from src.dbtools.adapters.repositories.async_neo4j import AsyncNeo4j

from typing import TYPE_CHECKING
if TYPE_CHECKING:
    from typing import AsyncGenerator
    from asyncio import AbstractEventLoop
    from neo4j import Transaction, Record


class TeamRepository(ABC):

    @abstractmethod
    async def add(self, team: Team):
        raise NotImplementedError

    @abstractmethod
    async def get(self, name: str) -> Team:
        raise NotImplementedError

    @abstractmethod
    async def get_all(self) -> "AsyncGenerator[Team]":
        yield None  # required for typing
        raise NotImplementedError


class FakeTeamRepository(TeamRepository):
    def __init__(self):
        self._teams = set()

    async def add(self, team: Team):
        self._teams.add(team)

    async def get(self, name: str) -> Team:
        return next(t for t in self._teams if t.name == name)

    async def get_all(self) -> "AsyncGenerator[Team]":
        for team in self._teams:
            yield team


class Neo4jTeamRepository(TeamRepository):

    def __init__(self, tx: "Transaction", loop: "AbstractEventLoop"):
        super().__init__()
        self.neo4j = AsyncNeo4j(tx, loop)

    async def add(self, team: Team):
        record: "Record" = await self.neo4j.single(queries['add_team'], name=team.name, fullname=team.fullname)
        team.id = record['team']['id']

    async def get(self, name: str) -> Team:
        record: "Record" = await self.neo4j.single(queries['get_team'], name=name)
        return Team(
            id=record['team']['id'],
            name=record['team']['name'],
            fullname=record['team']['fullname']
        ) if record else None

    async def get_all(self) -> "AsyncGenerator[Team]":
        async for record in self.neo4j.records(queries['get_all_teams']):
            yield Team(
                id=record['team']['id'],
                name=record['team']['name'],
                fullname=record['team']['fullname']
            )
