from asyncio import CancelledError
from contextlib import asynccontextmanager
from typing import AsyncGenerator

from neo4j import AsyncTransaction, AsyncSession

from src.breedgraph.adapters.neo4j.constraints.constraints import Neo4jConstraintsHandler
from src.breedgraph.adapters.neo4j.driver import Neo4jAsyncDriver

from src.breedgraph.domain.model.controls import ReadRelease
from src.breedgraph.service_layer.infrastructure.constraints import AbstractConstraintsHandler

from src.breedgraph.service_layer.repositories.holder import AbstractRepoHolder
from src.breedgraph.adapters.neo4j.repositories.holder import Neo4jRepoHolder

from src.breedgraph.service_layer.application import (
    AbstractAccessControlService,
    OntologyApplicationService,
    GermplasmApplicationService,
    AbstractExtraAggregateService
)
from src.breedgraph.adapters.neo4j.services import (
    Neo4jAccessControlService, Neo4jOntologyPersistenceService, Neo4jGermplasmPersistenceService, Neo4jExtraAggregateService
)
from src.breedgraph.service_layer.persistence import (
    OntologyPersistenceService, GermplasmPersistenceService
)


from src.breedgraph.service_layer.infrastructure.unit_of_work import AbstractUnitHolder, AbstractUnitOfWorkFactory

from src.breedgraph.domain.model.accounts import OntologyRole

from src.breedgraph.adapters.neo4j.cypher import queries

import logging
logger = logging.getLogger(__name__)


class Neo4jUnitHolder(AbstractUnitHolder):
    def __init__(
            self,
            tx: AsyncTransaction,
            constraints: AbstractConstraintsHandler,
            controls: AbstractAccessControlService,
            ontology: OntologyApplicationService,
            germplasm: GermplasmApplicationService,
            extra: AbstractExtraAggregateService,
            repositories: AbstractRepoHolder
    ):
        self.tx = tx
        self.constraints = constraints
        self.controls = controls
        self.ontology = ontology
        self.germplasm = germplasm
        self.extra = extra
        self.repositories: AbstractRepoHolder = repositories

    async def commit(self):
        logger.debug("Transaction commit")
        await self.repositories.update_all_seen()
        await self.tx.commit()

    async def rollback(self):
        logger.debug("Transaction roll back (explicit)")
        await self.tx.rollback()

    async def db_is_empty(self) -> bool:
        result = await self.tx.run(queries['infrastructure']['is_empty'])
        return (await result.single())["empty"]

    async def create_constraints(self):
        logger.info("Creating constraints...")
        constraints = queries['infrastructure']['create_constraints']
        for constraint in constraints.split(';\n'):
            logger.debug(f"Creating constraint: {constraint}")
            await self.tx.run(constraint)


class Neo4jUnitOfWorkFactory(AbstractUnitOfWorkFactory):

    @asynccontextmanager
    async def _get_uow(
            self,
            user_id: int = None,
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

        logger.debug("Initialize constraints handler")
        constraints_handler = Neo4jConstraintsHandler(tx, user_id=user_id)

        logger.debug("Initialize user context and access control")
        access_control_service = Neo4jAccessControlService(tx)
        await access_control_service.initialize_user_context(user_id=user_id)

        logger.debug("Initialize repositories holder")
        repo_holder = Neo4jRepoHolder(
            tx=tx,
            access_control_service=access_control_service,
            redacted=redacted,
            release=release
        )

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
            constraints=constraints_handler,
            controls=access_control_service,
            repositories=repo_holder,
            ontology=ontology_service,
            germplasm=germplasm_service,
            extra=extra_aggregate_service
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
