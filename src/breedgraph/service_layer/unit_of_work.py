import logging

from abc import ABC, abstractmethod
from neo4j import AsyncGraphDatabase


from asyncio import CancelledError

# Typing only
from typing import Self
from neo4j import AsyncDriver, AsyncTransaction, AsyncSession
from src.breedgraph.adapters.repositories.base import BaseRepository
from src.breedgraph.adapters.repositories.controlled import ControlledRepository
from src.breedgraph.adapters.repositories.accounts import Neo4jAccountRepository
from src.breedgraph.adapters.repositories.organisations import Neo4jOrganisationsRepository
from src.breedgraph.adapters.repositories.ontologies import Neo4jOntologyRepository
from src.breedgraph.adapters.repositories.germplasms import Neo4jGermplasmRepository
from src.breedgraph.config import get_bolt_url, get_graphdb_auth, DATABASE_NAME
from src.breedgraph.domain.events import Event
from src.breedgraph.domain.model.accounts import AccountStored

logger = logging.getLogger(__name__)

from contextlib import asynccontextmanager

from typing import List, Callable


class AbstractRepoHolder(ABC):
    accounts: BaseRepository
    organisations: BaseRepository
    ontologies: BaseRepository
    germplasm: ControlledRepository

    @abstractmethod
    async def commit(self):
        raise NotImplementedError

    @abstractmethod
    async def rollback(self):
        raise NotImplementedError

    def collect_events(self):  # todo generalise for all attributes that are BaseRepository
        for account in self.accounts.seen:
            while account.events:
                yield account.events.pop(0)
        for organisation in self.organisations.seen:
            while organisation.events:
                yield organisation.events.pop(0)
        for ontology in self.ontologies.seen:
            while ontology.events:
                yield ontology.events.pop(0)
        for germplasm in self.germplasm.seen:
            while germplasm.events:
                yield germplasm.events.pop(0)


class AbstractUnitOfWork(ABC):
    events: List[Event] = list()

    @asynccontextmanager
    async def get_repositories(self, user_id: int = None):
        async with self._get_repositories(user_id) as repo_holder:
            try:
                yield repo_holder
            finally:
                logger.debug("Collect events from repositories")
                self.events.extend(repo_holder.collect_events())

    @abstractmethod
    @asynccontextmanager
    async def _get_repositories(self, user_id: int = None) -> AbstractRepoHolder:
        raise NotImplementedError

    def collect_events(self):
        while self.events:
            yield self.events.pop(0)

class Neo4jRepoHolder(AbstractRepoHolder):
    def __init__(self, tx: AsyncTransaction, account: AccountStored = None):
        self.tx = tx
        self.accounts = Neo4jAccountRepository(self.tx)
        self.organisations = Neo4jOrganisationsRepository(self.tx)
        self.ontologies = Neo4jOntologyRepository(self.tx)
        if account is not None:
            self.germplasm = Neo4jGermplasmRepository(self.tx, user_id = account.user.id)
        else:
            self.germplasm = Neo4jGermplasmRepository(self.tx)

    async def commit(self):
        await self.accounts.update_seen()
        await self.organisations.update_seen()
        await self.ontologies.update_seen()
        await self.germplasm.update_seen()
        logger.debug("Transaction commit")
        await self.tx.commit()

    async def rollback(self):
        logger.debug("Transaction roll back (explicit)")
        await self.tx.rollback()

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

    @asynccontextmanager
    async def _get_repositories(self, account: AccountStored = None):
        logger.debug("Start neo4j session")
        session: AsyncSession = self.driver.session()
        logger.debug("Begin neo4j transaction")
        tx: AsyncTransaction = await session.begin_transaction()
        repo_holder = Neo4jRepoHolder(tx=tx, account=account)
        try:
            yield repo_holder
        finally:
            try:
                logger.debug("Transaction close (triggers roll back if not already closed)")
                await tx.close()
            except CancelledError:
                logger.debug("Operation cancelled, cancel session and raise")
                session.cancel()
                raise
            finally:
                logger.debug("Session close")
                await session.close()

