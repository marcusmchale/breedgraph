from abc import ABC, abstractmethod
from collections import defaultdict

from src.dbtools.adapters.repositories.cypher import queries
from src.dbtools.adapters.repositories.async_neo4j import AsyncNeo4j

from typing import TYPE_CHECKING

if TYPE_CHECKING: # on 
    from asyncio import AbstractEventLoop
    from src.dbtools.domain.model.accounts import UserRegistered
    from neo4j import Transaction, Record


class AllowedEmailRepository(ABC):

    @abstractmethod
    async def add(self, user: "UserRegistered", email: str):
        raise NotImplementedError

    @abstractmethod
    async def get(self, email: str) -> str:
        raise NotImplementedError

    @abstractmethod
    async def remove(self, user: "UserRegistered", email: str):
        raise NotImplementedError


class FakeAllowedEmailRepository(AllowedEmailRepository):

    def __init__(self):
        self.allowed = defaultdict(set)

    async def add(self, user: "UserRegistered", email: str):
        self.allowed[user.username].add(email)

    async def get(self, email: str) -> str:
        for emails in self.allowed.values():
            for e in emails:
                if e.casefold == email.casefold():
                    return e

    def remove(self, user: "UserRegistered", email: str):
        self.allowed[user.username].remove(email)


class Neo4jAllowedEmailRepository(AllowedEmailRepository):

    def __init__(self, tx: "Transaction", loop: "AbstractEventLoop"):
        super().__init__()
        self.neo4j = AsyncNeo4j(tx, loop)

    async def add(self, user: "UserRegistered", email: str):
        await self.neo4j.run(
            queries['add_email'],
            username_lower=user.username_lower,
            email=email
        )

    async def get(self, email: str) -> str:
        record: Record = await self.neo4j.single(
            queries['get_email'],
            email=email
        )
        return record['email'] if record else None

    async def remove(self, user: "UserRegistered", email: str):
        await self.neo4j.run(
            queries['remove_email'],
            admin_name_lower=user.username_lower,
            email=email
        )
