import logging

from abc import ABC, abstractmethod
from neo4j import AsyncGraphDatabase


from asyncio import CancelledError

from neo4j import AsyncDriver, AsyncTransaction, AsyncSession

from src.breedgraph import views

from src.breedgraph.config import get_bolt_url, get_graphdb_auth, DATABASE_NAME
from src.breedgraph.domain.events import Event
from src.breedgraph.domain.model.controls import ReadRelease, Access

from src.breedgraph.adapters.repositories.arrangements import Neo4jArrangementsRepository
from src.breedgraph.adapters.repositories.base import BaseRepository
from src.breedgraph.adapters.repositories.controlled import ControlledRepository
from src.breedgraph.adapters.repositories.accounts import Neo4jAccountRepository
from src.breedgraph.adapters.repositories.datasets import Neo4jDatasetsRepository
from src.breedgraph.adapters.repositories.organisations import Neo4jOrganisationsRepository
from src.breedgraph.adapters.repositories.ontologies import Neo4jOntologyRepository
from src.breedgraph.adapters.repositories.germplasms import Neo4jGermplasmRepository
from src.breedgraph.adapters.repositories.people import Neo4jPeopleRepository
from src.breedgraph.adapters.repositories.programs import Neo4jProgramsRepository
from src.breedgraph.adapters.repositories.references import Neo4jReferencesRepository
from src.breedgraph.adapters.repositories.regions import Neo4jRegionsRepository

logger = logging.getLogger(__name__)

from contextlib import asynccontextmanager

from typing import List, Set

class AbstractRepoHolder(ABC):
    accounts: BaseRepository
    organisations: BaseRepository
    ontologies: BaseRepository
    germplasm: ControlledRepository

    arrangements: ControlledRepository
    datasets: ControlledRepository
    germplasms: ControlledRepository
    people: ControlledRepository
    programs: ControlledRepository
    references: ControlledRepository
    regions: ControlledRepository

    @abstractmethod
    async def commit(self):
        raise NotImplementedError

    @abstractmethod
    async def rollback(self):
        raise NotImplementedError

    def collect_events(self):
        for attr, value in self.__dict__.items():
            if isinstance(value, BaseRepository):
                for aggregate in value.seen:
                    while aggregate.events:
                        yield aggregate.events.pop(0)


class AbstractUnitOfWork(ABC):
    events: List[Event] = list()

    @asynccontextmanager
    async def get_repositories(self, user_id: int = None, redacted: bool = True):
        async with self._get_repositories(user_id, redacted) as repo_holder:
            try:
                yield repo_holder
            finally:
                logger.debug("Collect events from repositories")
                self.events.extend(repo_holder.collect_events())

    @abstractmethod
    @asynccontextmanager
    async def _get_repositories(self, user_id: int = None, redacted: bool = True) -> AbstractRepoHolder:
        raise NotImplementedError

    def collect_events(self):
        while self.events:
            yield self.events.pop(0)

class Neo4jRepoHolder(AbstractRepoHolder):
    def __init__(
            self,
            tx: AsyncTransaction,
            user_id: int = None,
            redacted: bool = True,
            read_teams: Set[int] = None,
            write_teams: Set[int] = None,
            admin_teams: Set[int] = None,
            curate_teams: Set[int] = None,
            release: ReadRelease = ReadRelease.PRIVATE
    ):
        self.tx = tx
        self.accounts = Neo4jAccountRepository(self.tx)
        self.organisations = Neo4jOrganisationsRepository(self.tx, user_id=user_id, redacted=redacted)
        self.ontologies = Neo4jOntologyRepository(self.tx)
        # The below are controlled repositories so require account read/write/curate/admin teams
        # and the default release for new entries
        repo_params = {
            'tx': self.tx,
            'user_id': user_id,
            'redacted': redacted,
            'read_teams':read_teams,
            'write_teams': write_teams,
            'curate_teams': curate_teams,
            'admin_teams': admin_teams,
            'release': release
        }
        self.arrangements = Neo4jArrangementsRepository(**repo_params)
        self.datasets = Neo4jDatasetsRepository(**repo_params)
        self.germplasms = Neo4jGermplasmRepository(**repo_params)
        self.people = Neo4jPeopleRepository(**repo_params)
        self.programs = Neo4jProgramsRepository(**repo_params)
        self.references = Neo4jReferencesRepository(**repo_params)
        self.regions = Neo4jRegionsRepository(**repo_params)

    async def commit(self):
        logger.debug("Update seen by all repositories")
        await self.accounts.update_seen()
        await self.organisations.update_seen()
        await self.ontologies.update_seen()
        await self.arrangements.update_seen()
        await self.datasets.update_seen()
        await self.germplasms.update_seen()
        await self.people.update_seen()
        await self.programs.update_seen()
        await self.references.update_seen()
        await self.regions.update_seen()
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
    async def _get_repositories(self, user_id: int = None, redacted: bool = True):
        logger.debug("Start neo4j session")
        session: AsyncSession = self.driver.session()
        logger.debug("Begin neo4j transaction")
        tx: AsyncTransaction = await session.begin_transaction()

        if user_id is not None:
            access_teams = await views.accounts.access_teams(uow=self, user=user_id)
        else:
            access_teams = {'read_teams': [], 'write_teams': [], 'curate_teams': [], 'admin_teams': []}

        repo_holder = Neo4jRepoHolder(tx=tx, user_id=user_id, redacted= redacted, **access_teams)
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

