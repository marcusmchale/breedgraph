from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from contextlib import asynccontextmanager
from pathlib import Path

from breedgraph.adapters.neo4j.services import Neo4jFileArchivalService
from breedgraph.entrypoints.fastapi.middleware import setup_middlewares

from breedgraph.entrypoints.fastapi.redirect import router as redirect_router
from breedgraph.entrypoints.fastapi.security import router as security_router
from breedgraph.entrypoints.fastapi.downloads import router as download_router
from breedgraph.entrypoints.fastapi.archive import router as archive_router
from breedgraph.entrypoints.fastapi.retention import router as retention_router
from breedgraph.entrypoints.fastapi.analysis_jobs import router as analysis_jobs_router
from breedgraph.entrypoints.fastapi.map_jobs import router as map_jobs_router

from breedgraph.entrypoints.fastapi.graphql_endpoint import router as graphql_router
from breedgraph.entrypoints.fastapi.graphql.schema import create_graphql_schema

from breedgraph import bootstrap, config
from breedgraph.service_layer.infrastructure.brute_force_protection import BruteForceProtectionService
from breedgraph.adapters.nominatim import NominatimGeocodingService

from breedgraph.service_layer.messagebus import MessageBus
from breedgraph.service_layer.application.terms_of_use import load_legal_text
from breedgraph.service_layer.application.acceptance_tokens import AcceptanceTokens

import logging

logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(fast_api_app: FastAPI):
    logger.debug("Application startup")

    logger.debug("Load messaging bus")
    bus: MessageBus = await bootstrap.bootstrap(archival_service=Neo4jFileArchivalService)
    fast_api_app.bus = bus

    if hasattr(bus.uow_factory, "driver"):
        logger.debug("Check the database's Cypher")
        await bus.uow_factory.driver.check_cypher_language()  # before anything runs a query

    logger.info("Starting event processors")
    await bus.start()  # start event process workers
    if bus.map_regions is not None:
        await bus.map_regions.start()  # resume fetching detailed maps

    logger.debug("Load brute force protection service")
    brute_force_service = BruteForceProtectionService(state_store=bus.state_store)
    fast_api_app.brute_force_service = brute_force_service

    logger.debug("Load geocoding service")
    fast_api_app.geocoding_service = NominatimGeocodingService()

    logger.debug("Load graphql schema")
    graphql_schema = create_graphql_schema()
    fast_api_app.graphql_schema = graphql_schema

    # the Terms of Use everyone accepts, the privacy notice anyone may read before them, and the signer of what people
    # accept (docs/licences.md §4)
    fast_api_app.terms_of_use = load_legal_text(config.TERMS_OF_USE_PATH)
    fast_api_app.privacy_notice = load_legal_text(config.PRIVACY_NOTICE_PATH)
    fast_api_app.acceptance_tokens = AcceptanceTokens(
        secret_key=config.SECRET_KEY,
        salt=config.ACCEPTANCE_SALT,
        signed_in_minutes=config.ACCEPTANCE_EXPIRES_SIGNED_IN,
        anonymous_minutes=config.ACCEPTANCE_EXPIRES_ANONYMOUS
    )

    yield

    logger.info("Start shutting down")
    if bus is not None:
        if bus.map_regions is not None:
            logger.info("Stopping map region fetches")
            await bus.map_regions.stop()
        if hasattr(bus.uow_factory, "driver"):
            logger.info("Closing driver")
            await bus.uow_factory.driver.close()
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
# Map tiles (scripts/map_tiles.py and adapters/pmtiles/map_regions.py), served by nginx in production; here for
# development, read in ranges. Until the script has run there are none, and each request is answered 404.
Path(config.MAP_TILES_PATH).mkdir(parents=True, exist_ok=True)
app.mount("/tiles", StaticFiles(directory=config.MAP_TILES_PATH), name="tiles")

## Internal services
# Local network service
app.include_router(archive_router)
# Cron job to trigger file cleanup
app.include_router(retention_router)
# Analysis worker
app.include_router(analysis_jobs_router)
# Map worker
app.include_router(map_jobs_router)

logger.debug('Started')