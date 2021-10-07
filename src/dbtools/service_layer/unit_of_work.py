from abc import ABC, abstractmethod
import asyncio
from neo4j import GraphDatabase, Transaction, Session
from asyncio import AbstractEventLoop, get_event_loop
from src.dbtools.adapters.repositories.accounts import BaseAccountRepository, Neo4jAccountRepository
from src.dbtools.adapters.neo4j.async_neo4j import AsyncNeo4j
from src.dbtools.config import get_bolt_url, get_graphdb_auth, DATABASE_NAME, MAX_WORKERS

from typing import TYPE_CHECKING
if TYPE_CHECKING:
    from concurrent.futures import ThreadPoolExecutor

import logging


class AbstractUnitOfWork(ABC):
    accounts: BaseAccountRepository

    def __init__(self):
        self.lock = asyncio.Lock()

    async def __aenter__(self) -> 'AbstractUnitOfWork':
        await self.lock.acquire()
        # get an async lock to avoid concurrency issues with repository instances
        # this is still not thread safe, consider thread locking if using multi-threading at any higher value
        return self

    async def __aexit__(self, *args):
        await self.close()  # roll back any changes if not committed
        self.lock.release()

    @abstractmethod
    async def commit(self):
        raise NotImplementedError

    @abstractmethod
    async def rollback(self):
        raise NotImplementedError

    @abstractmethod
    async def close(self):
        raise NotImplementedError

    def collect_events(self):
        for account in self.accounts.seen:
            while account.events:
                yield account.events.pop(0)


class Neo4jUnitOfWork(AbstractUnitOfWork):

    def __init__(
            self,
            thread_pool: "ThreadPoolExecutor",
            database_name=DATABASE_NAME
    ):
        super().__init__()
        self.driver = GraphDatabase.driver(
            get_bolt_url(),
            auth=get_graphdb_auth(),
            database=database_name,
            connection_timeout=5,
            connection_acquisition_timeout=5,
            max_transaction_retry_time=5
        )
        self.thread_pool = thread_pool

    async def __aenter__(self):
        self._loop: AbstractEventLoop = get_event_loop()
        self._session: Session = await self._loop.run_in_executor(self.thread_pool, self.driver.session)
        logging.debug('Started session')
        self._tx: Transaction = await self._loop.run_in_executor(self.thread_pool, self._session.begin_transaction)
        logging.debug('Started transaction')
        self.neo4j = AsyncNeo4j(self._tx, self._loop, self.thread_pool)
        await super().__aenter__()  # async lock after obtaining tx
        # allows next async uow to have a tx ready to go when lock is cleared
        self.accounts = Neo4jAccountRepository(self.neo4j)
        return self

    async def commit(self):
        logging.debug("Updating changed accounts")
        await self.accounts.update_seen()
        logging.debug("Committing transaction")
        await self._loop.run_in_executor(self.thread_pool, self._tx.commit)

    async def rollback(self):
        logging.debug("Rolling back transaction")
        await self._loop.run_in_executor(self.thread_pool, self._tx.rollback)

    async def close(self):
        logging.debug("Closing transaction")
        await self._loop.run_in_executor(self.thread_pool, self._tx.close)
        logging.debug("Closing session")
        await self._loop.run_in_executor(self.thread_pool, self._session.close)
