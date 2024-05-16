import logging

from abc import ABC, abstractmethod
from neo4j import AsyncGraphDatabase


from asyncio import CancelledError

# Typing only
from typing import Self
from neo4j import AsyncDriver, AsyncTransaction, AsyncSession
from src.breedgraph.adapters.repositories.base import BaseRepository
from src.breedgraph.adapters.repositories.accounts import Neo4jAccountRepository
from src.breedgraph.adapters.repositories.organisations import Neo4jOrganisationRepository
from src.breedgraph.config import get_bolt_url, get_graphdb_auth, DATABASE_NAME

logger = logging.getLogger(__name__)

class AbstractUnitOfWork(ABC):
    accounts: BaseRepository
    organisations: BaseRepository

    async def __aenter__(self) -> Self:
        return self

    async def __aexit__(self, *args):  # todo investigate async cancellation behaviour (write some tests)
        logger.debug("Close unit of work (roll back unless committed)")
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
        logger.debug("Build new neo4j driver")
        self.driver: AsyncDriver = AsyncGraphDatabase.driver(
            get_bolt_url(),
            auth=get_graphdb_auth(),
            database=DATABASE_NAME,
            connection_timeout=5,
            connection_acquisition_timeout=5,
            max_transaction_retry_time=5
        )

    async def __aenter__(self) -> Self:
        logger.debug("Start new neo4j session")
        self._session: AsyncSession = self.driver.session()
        logger.debug("Begin neo4j transaction")
        self.tx: AsyncTransaction = await self._session.begin_transaction()
        self.accounts = Neo4jAccountRepository(self.tx)
        self.organisations = Neo4jOrganisationRepository(self.tx)
        return self

    async def __aexit__(self, *args):
        try:
            logger.debug("Transaction close (triggers roll back if not already closed)")
            await self.tx.close()
        except CancelledError:
            logger.debug("Operation cancelled, cancel session and raise")
            self._session.cancel()
            raise
        finally:
            logger.debug("Session close")
            await self._session.close()

    async def commit(self):
        logger.debug("Accounts update")
        await self.accounts.update_seen()
        await self.organisations.update_seen()
        logger.debug("Transaction commit")
        await self.tx.commit()

    async def rollback(self):
        logger.debug("Transaction roll back (explicit)")
        await self.tx.rollback()


