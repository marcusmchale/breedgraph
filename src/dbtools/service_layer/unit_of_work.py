from abc import ABC, abstractmethod
import asyncio
from neo4j import GraphDatabase, Transaction
from asyncio import AbstractEventLoop, get_event_loop
from dbtools.adapters.repositories import allowed_emails, teams, accounts
from dbtools.config import get_bolt_url, get_graphdb_auth

import logging


class AbstractUnitOfWork(ABC):
    emails: allowed_emails.AllowedEmailRepository
    teams: teams.TeamRepository
    accounts: accounts.AccountRepository

    def __init__(self):
        self.lock = asyncio.Lock()  # using an sync lock here

    async def __aenter__(self) -> 'AbstractUnitOfWork':
        await self.lock.acquire()
        # get an async lock here to avoid concurrency issues with repository instances
        # this is still not thread safe, consider thread locking if using multi-threading at any higher level
        # threads are currently only being used within the repositories
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

    def __init__(self):
        super().__init__()
        self.driver = GraphDatabase.driver(
            get_bolt_url(),
            auth=get_graphdb_auth(),
            connection_timeout=5,
            connection_acquisition_timeout=5,
            max_transaction_retry_time=5
        )

    async def __aenter__(self):
        self.loop: AbstractEventLoop = get_event_loop()
        self.session = await self.loop.run_in_executor(None, self.driver.session)
        logging.debug('Started session')
        self.tx = await self.loop.run_in_executor(None, self.session.begin_transaction)
        logging.debug('Started transaction')
        await super().__aenter__()  # async lock after obtaining tx
        # allows next async uow to have a tx ready to go when lock is cleared
        self.emails = allowed_emails.Neo4jAllowedEmailRepository(self.tx, self.loop)
        self.teams = teams.Neo4jTeamRepository(self.tx, self.loop)
        self.accounts = accounts.Neo4jAccountRepository(self.tx, self.loop)
        return self

    async def commit(self):
        await self.accounts.update_seen()
        await self.loop.run_in_executor(None, self.tx.commit)
        logging.debug("Committed transaction")

    async def rollback(self):
        await self.loop.run_in_executor(None, self.tx.rollback)
        logging.debug("Rolled back transaction")

    async def close(self):
        await self.loop.run_in_executor(None, self.tx.close)  # rolls back any outstanding transactions
        logging.debug("Closed transaction")
        await self.loop.run_in_executor(None, self.session.close)  # rolls back any outstanding transactions
        logging.debug("Closed session")
