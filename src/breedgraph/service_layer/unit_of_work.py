import logging

from abc import ABC, abstractmethod
from src.breedgraph.adapters.neo4j.driver import get_driver
from asyncio import CancelledError

# Typing only
from typing import Self
from neo4j import AsyncDriver, AsyncTransaction, AsyncSession
from src.breedgraph.adapters.repositories.accounts import BaseAccountRepository, Neo4jAccountRepository


class AbstractUnitOfWork(ABC):
    accounts: BaseAccountRepository

    async def __aenter__(self) -> Self:
        return self

    async def __aexit__(self, *args):  # todo investigate async cancellation behaviour (write some tests)
        logging.debug("Close unit of work (roll back unless committed)")
        await self.rollback()  # note: exceptions inside aexit will replace any that triggerred the exit

    @abstractmethod
    async def commit(self):
        raise NotImplementedError

    @abstractmethod
    async def rollback(self):
        raise NotImplementedError

    def collect_events(self):
        for account in self.accounts.seen:
            while account.events:
                yield account.events.pop(0)


class Neo4jUnitOfWork(AbstractUnitOfWork):

    def __init__(self):
        super().__init__()
        self.driver: AsyncDriver = get_driver()

    async def __aenter__(self) -> Self:
        self._session: AsyncSession = self.driver.session()
        self.tx: AsyncTransaction = await self._session.begin_transaction()
        self.accounts = Neo4jAccountRepository(self.tx)
        return self

    async def __aexit__(self, *args):
        try:
            logging.debug("Transaction close (triggers roll back if not already closed)")
            await self.tx.close()
        except CancelledError:
            logging.debug("Operation cancelled, cancel session and raise")
            self._session.cancel()
            raise
        finally:
            logging.debug("Session close")
            await self._session.close()

    async def commit(self):
        logging.debug("Accounts update")
        await self.accounts.update_seen()
        logging.debug("Transaction commit")
        await self.tx.commit()

    async def rollback(self):
        logging.debug("Transaction roll back (explicit)")
        await self.tx.rollback()


