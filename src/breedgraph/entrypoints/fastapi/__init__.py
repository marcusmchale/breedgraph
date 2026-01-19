from fastapi import FastAPI
from contextlib import asynccontextmanager

from src.breedgraph.entrypoints.fastapi.middleware import setup_middlewares

from src.breedgraph.entrypoints.fastapi.redirect import router as redirect_router
from src.breedgraph.entrypoints.fastapi.security import router as security_router
from src.breedgraph.entrypoints.fastapi.downloads import router as download_router

from src.breedgraph.entrypoints.fastapi.graphql_endpoint import router as graphql_router
from src.breedgraph.entrypoints.fastapi.graphql.schema import create_graphql_schema

from src.breedgraph import bootstrap
from src.breedgraph.service_layer.infrastructure.brute_force_protection import BruteForceProtectionService

from src.breedgraph.service_layer.messagebus import MessageBus

import logging

logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(fast_api_app: FastAPI):
    logger.debug("Application startup")

    logger.debug("Load messaging bus")
    bus: MessageBus = await bootstrap.bootstrap()
    fast_api_app.bus = bus

    logger.info("Starting event processors")
    await bus.start()  # start event process workers

    logger.debug("Load brute force protection service")
    brute_force_service = BruteForceProtectionService(state_store=bus.state_store)
    fast_api_app.brute_force_service = brute_force_service

    logger.debug("Load graphql schema")
    graphql_schema = create_graphql_schema()
    fast_api_app.graphql_schema = graphql_schema

    yield

    logger.info("Start shutting down")
    if bus is not None:
        if hasattr(bus.uow, "driver"):
            logger.info("Closing driver")
            await bus.uow.driver.close()
        if hasattr(bus.state_store, "connection"):
            logger.info("Closing state_store connection pool")
            await bus.state_store.connection.aclose()
        logger.info("Stopping event processors")
        await bus.stop()
    logger.info("Finished shutting down")


logger.debug("Start FastAPI app")
app = FastAPI(lifespan=lifespan)

setup_middlewares(app)

app.include_router(redirect_router)
app.include_router(security_router)
app.include_router(graphql_router)
app.include_router(download_router)

logger.debug('Started')