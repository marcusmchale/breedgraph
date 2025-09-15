from asyncio import CancelledError
from contextlib import asynccontextmanager
from typing import AsyncGenerator

from neo4j import AsyncTransaction, AsyncDriver, AsyncGraphDatabase, AsyncSession

from src.breedgraph.config import get_bolt_url, get_graphdb_auth, DATABASE_NAME, MAIL_USERNAME, MAIL_HOST
from src.breedgraph.domain.model.controls import ReadRelease

from src.breedgraph.service_layer.queries.views import AbstractViewsHolder
from src.breedgraph.adapters.neo4j.views.base import Neo4jViewsHolder

from src.breedgraph.service_layer.repositories.holder import AbstractRepoHolder
from src.breedgraph.adapters.neo4j.repositories.holder import Neo4jRepoHolder

from src.breedgraph.service_layer.application import (
    AbstractAccessControlService,
    OntologyApplicationService,
    GermplasmApplicationService
)
from src.breedgraph.adapters.neo4j.services import (
    Neo4jAccessControlService, Neo4jOntologyPersistenceService, Neo4jGermplasmPersistenceService
)
from src.breedgraph.service_layer.persistence import (
    OntologyPersistenceService, GermplasmPersistenceService
)
from src.breedgraph.service_layer.infrastructure.unit_of_work import AbstractUnitHolder, AbstractUnitOfWork

from src.breedgraph.adapters.neo4j.cypher import queries

import logging
logger = logging.getLogger(__name__)


class Neo4jUnitHolder(AbstractUnitHolder):
    def __init__(
            self,
            tx: AsyncTransaction,
            views: AbstractViewsHolder,
            controls: AbstractAccessControlService,
            ontology: OntologyApplicationService,
            germplasm: GermplasmApplicationService,
            repositories: AbstractRepoHolder
    ):
        self.tx = tx
        self.views = views
        self.controls = controls
        self.ontology = ontology
        self.germplasm = germplasm
        self.repositories: AbstractRepoHolder = repositories

    async def commit(self):
        logger.debug("Transaction commit")
        await self.repositories.update_all_seen()
        await self.tx.commit()

    async def rollback(self):
        logger.debug("Transaction roll back (explicit)")
        await self.tx.rollback()

    async def db_is_empty(self) -> bool:
        result = await self.tx.run(queries['views']['is_empty'])
        return (await result.single())["empty"]


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
    async def _get_uow(
            self,
            user_id: int = None,
            redacted: bool = True,
            release: ReadRelease = ReadRelease.PRIVATE
    ) -> AsyncGenerator[Neo4jUnitHolder, None]:
        logger.debug("Start neo4j session")
        session: AsyncSession = self.driver.session()
        logger.debug("Begin neo4j transaction")
        tx: AsyncTransaction = await session.begin_transaction()

        views_holder = Neo4jViewsHolder(tx)
        access_teams = await views_holder.access_teams(user=user_id)
        access_control_service = Neo4jAccessControlService(tx)
        repo_holder = Neo4jRepoHolder(
            tx=tx,
            access_control_service=access_control_service,
            user_id=user_id,
            redacted=redacted,
            release=release,
            access_teams=access_teams
        )

        if user_id is not None:
            user = await views_holder.get_user(user=user_id)
        else:
            user = None

        ontology_persistence_service: OntologyPersistenceService = Neo4jOntologyPersistenceService(tx)
        ontology_service = OntologyApplicationService(
            persistence_service=ontology_persistence_service,
            user_id=user_id,
            role=user.ontology_role if user else None
        )
        germplasm_persistence_service: GermplasmPersistenceService = Neo4jGermplasmPersistenceService(tx)
        germplasm_service = GermplasmApplicationService(
            persistence_service=germplasm_persistence_service,
            access_control_service=access_control_service,
            user_id=user_id,
            access_teams=access_teams,
            release=release
        )

        unit_holder = Neo4jUnitHolder(
            tx=tx,
            views=views_holder,
            controls=access_control_service,
            repositories=repo_holder,
            ontology=ontology_service,
            germplasm=germplasm_service
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
