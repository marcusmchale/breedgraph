from fastapi import FastAPI
from contextlib import asynccontextmanager

from src.breedgraph.entrypoints.fastapi.middleware import setup_middlewares
from src.breedgraph.entrypoints.fastapi.redirect import router as redirect_router
from src.breedgraph.entrypoints.fastapi.security import router as security_router
from src.breedgraph.entrypoints.fastapi.graphql_endpoint import router as graphql_router
from src.breedgraph.entrypoints.fastapi.graphql.schema import create_graphql_schema

from src.breedgraph import bootstrap
from src.breedgraph.service_layer.infrastructure.authentication import AbstractAuthService, ItsDangerousAuthService

from src.breedgraph.service_layer.messagebus import MessageBus

import logging

logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(fast_api_app: FastAPI):
    logger.debug("Application startup")

    logger.debug("Load auth service")
    auth_service: AbstractAuthService = ItsDangerousAuthService()
    fast_api_app.auth_service = auth_service

    logger.debug("Load messaging bus")
    bus: MessageBus = await bootstrap.bootstrap(auth_service=auth_service)
    fast_api_app.bus = bus

    logger.debug("Load graphql schema")
    graphql_schema = create_graphql_schema()
    fast_api_app.graphql_schema = graphql_schema

    yield

    logger.info("Start shutting down")
    if bus is not None:
        if hasattr(bus.uow, "driver"):
            logger.info("Closing Neo4j driver")
            await bus.uow.driver.close()
        logger.info("Closing Redis connection pool")
        await bus.read_model.connection.aclose()
    logger.info("Finished shutting down")


logger.debug("Start FastAPI app")
app = FastAPI(lifespan=lifespan)

setup_middlewares(app)

app.include_router(redirect_router)
app.include_router(security_router)
app.include_router(graphql_router)

logger.debug('Started')