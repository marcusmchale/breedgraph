from asyncio import CancelledError
from contextlib import asynccontextmanager
from typing import AsyncGenerator

from neo4j import AsyncTransaction, AsyncSession

from breedgraph.domain.events import Event

from breedgraph.domain.model.controls import ReadRelease
from breedgraph.domain.model.accounts import OntologyRole

from breedgraph.service_layer.application import (
    AbstractAccessControlService,
    OntologyApplicationService,
    GermplasmApplicationService,
    AbstractAggregateRestructuringService
)

from breedgraph.service_layer.infrastructure import (
    AbstractDependencyGuards,
    AbstractConstraintsHandler,
    AbstractUnitHolder,
    AbstractUnitOfWorkFactory
)

from breedgraph.service_layer.repositories import AbstractRepoHolder

from breedgraph.adapters.neo4j.services import (
    Neo4jAccessControlService,
    Neo4jOntologyPersistenceService,
    Neo4jGermplasmPersistenceService,
    Neo4jAggregateRestructuringService,
    Neo4jDependencyGuards
)
from breedgraph.adapters.neo4j.repositories.holder import Neo4jRepoHolder
from breedgraph.adapters.neo4j.constraints.constraints import Neo4jConstraintsHandler


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
            restructuring: AbstractAggregateRestructuringService,
            guards: AbstractDependencyGuards,
            constraints: AbstractConstraintsHandler,
            repositories: AbstractRepoHolder
    ):
        self.tx = tx
        self.committed = False
        self.controls = controls
        self.ontology = ontology
        self.germplasm = germplasm
        self.restructuring = restructuring
        self.guards = guards
        self.constraints = constraints
        self.repositories = repositories

    @classmethod
    async def create(
            cls,
            tx: AsyncTransaction,
            user_id: int | None = None,
            redacted: bool = True,
            release: ReadRelease = ReadRelease.PRIVATE
    ) -> "Neo4jUnitHolder":
        """Async factory that handles service initialization"""

        access_control_service = await Neo4jAccessControlService.create(tx, user_id=user_id)

        ontology_persistence = Neo4jOntologyPersistenceService(tx)
        ontology_role = (
            await ontology_persistence.get_user_ontology_role(user_id=user_id)
            if user_id else OntologyRole.VIEWER
        )
        ontology_service = OntologyApplicationService(
            persistence_service=ontology_persistence,
            user_id=user_id,
            role=ontology_role
        )

        germplasm_persistence = Neo4jGermplasmPersistenceService(tx)
        germplasm_service = GermplasmApplicationService(
            persistence_service=germplasm_persistence,
            access_control_service=access_control_service,
            release=release
        )

        restructuring = Neo4jAggregateRestructuringService(tx)
        guards = Neo4jDependencyGuards(tx)
        constraints = Neo4jConstraintsHandler(tx, user_id)
        repositories = Neo4jRepoHolder(tx, access_control_service, release=release, redacted=redacted)

        return cls(
            tx=tx,
            controls=access_control_service,
            ontology=ontology_service,
            germplasm=germplasm_service,
            restructuring=restructuring,
            guards=guards,
            constraints=constraints,
            repositories=repositories
        )

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
            user_id: int | None = None,
            redacted: bool = True,
            release: ReadRelease = ReadRelease.PRIVATE
    ) -> AsyncGenerator[Neo4jUnitHolder, None]:

        session: AsyncSession = self.driver.session()
        tx: AsyncTransaction = await session.begin_transaction()

        unit_holder = await Neo4jUnitHolder.create(
            tx=tx,
            user_id=user_id,
            redacted=redacted,
            release=release
        )

        try:
            yield unit_holder
        finally:
            try:
                await tx.close()
            except CancelledError:
                session.cancel()
                raise
            finally:
                await session.close()
