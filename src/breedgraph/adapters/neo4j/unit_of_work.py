from asyncio import CancelledError
from contextlib import asynccontextmanager
from typing import AsyncGenerator

from neo4j import AsyncTransaction, AsyncSession

from breedgraph.adapters.neo4j.constraints.constraints import Neo4jConstraintsHandler
from breedgraph.domain.events import Event

from breedgraph.domain.model.controls import ReadRelease
from breedgraph.service_layer.infrastructure.constraints import AbstractConstraintsHandler

from breedgraph.service_layer.repositories.holder import AbstractRepoHolder
from breedgraph.adapters.neo4j.repositories.holder import Neo4jRepoHolder

from breedgraph.service_layer.application import (
    AbstractAccessControlService,
    OntologyApplicationService,
    GermplasmApplicationService,
    AbstractExtraAggregateService
)
from breedgraph.adapters.neo4j.services import (
    Neo4jAccessControlService, Neo4jOntologyPersistenceService, Neo4jGermplasmPersistenceService, Neo4jExtraAggregateService
)
from breedgraph.service_layer.persistence import (
    OntologyPersistenceService, GermplasmPersistenceService
)


from breedgraph.service_layer.infrastructure.unit_of_work import AbstractUnitHolder, AbstractUnitOfWorkFactory

from breedgraph.domain.model.accounts import OntologyRole

from typing import List, Generator

import logging
logger = logging.getLogger(__name__)


class Neo4jUnitHolder(AbstractUnitHolder):
    def __init__(
            self,
            tx: AsyncTransaction,
            controls: AbstractAccessControlService,
            ontology: OntologyApplicationService,
            germplasm: GermplasmApplicationService,
            extra: AbstractExtraAggregateService,
            redacted: bool = True
    ):
        self.tx = tx
        self.committed = False

        self.controls = controls
        self.ontology = ontology
        self.germplasm = germplasm
        self.extra = extra

        logger.debug("Initialize repositories holder")
        self.repositories = Neo4jRepoHolder(tx, controls, redacted=redacted)

        logger.debug("Initialize constraints handler")
        self.constraints = Neo4jConstraintsHandler(tx, self.controls.user_id)


    def collect_events(self) -> Generator[Event, None, None]:
        yield from self.repositories.collect_events()
        yield from self.ontology.collect_events()
        yield from self.germplasm.collect_events()

    async def commit(self):
        logger.debug("Transaction commit")
        await self._commit_repositories()
        await self.tx.commit()
        self.committed = True

    async def rollback(self):
        logger.debug("Transaction roll back (explicit)")
        await self.tx.rollback()
        self.committed = False

    async def _commit_repositories(self):
        logger.debug("Update seen aggregates across all repositories")
        await self.repositories.accounts.update_seen()
        await self.repositories.organisations.update_seen()
        await self.repositories.arrangements.update_seen()
        await self.repositories.datasets.update_seen()
        await self.repositories.people.update_seen()
        await self.repositories.programs.update_seen()
        await self.repositories.references.update_seen()
        await self.repositories.regions.update_seen()
        await self.repositories.blocks.update_seen()


class Neo4jUnitOfWorkFactory(AbstractUnitOfWorkFactory):

    @asynccontextmanager
    async def _get_uow(
            self,
            user_id: int|None = None,
            redacted: bool = True,
            release: ReadRelease = ReadRelease.PRIVATE
    ) -> AsyncGenerator[Neo4jUnitHolder, None]:
        #todo set up parameters for uow creation
        # so we can get just what we need for uow
        # rather than loading everything every time

        logger.debug("Start neo4j session")
        session: AsyncSession = self.driver.session()

        logger.debug("Begin neo4j transaction")
        tx: AsyncTransaction = await session.begin_transaction()

        logger.debug("Initialize user context and access control")
        access_control_service = await Neo4jAccessControlService.create(tx, user_id=user_id)

        logger.debug("Initialize ontology service")
        ontology_persistence_service: OntologyPersistenceService = Neo4jOntologyPersistenceService(tx)
        if user_id:
            ontology_role = await ontology_persistence_service.get_user_ontology_role(user_id=user_id)
        else:
            ontology_role = OntologyRole.VIEWER

        ontology_service = OntologyApplicationService(
            persistence_service=ontology_persistence_service,
            user_id=user_id,
            role = ontology_role
        )

        logger.debug("Initialize germplasm service")
        germplasm_persistence_service: GermplasmPersistenceService = Neo4jGermplasmPersistenceService(tx)
        germplasm_service = GermplasmApplicationService(
            persistence_service=germplasm_persistence_service,
            access_control_service=access_control_service,
            release=release
        )

        logger.debug("initialize extra aggregate service")
        extra_aggregate_service: AbstractExtraAggregateService = Neo4jExtraAggregateService(tx)

        logger.debug("Build unit of work holder")
        unit_holder = Neo4jUnitHolder(
            tx=tx,
            controls=access_control_service,
            ontology=ontology_service,
            germplasm=germplasm_service,
            extra=extra_aggregate_service,
            redacted=redacted
        )
        try:
            yield unit_holder

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
