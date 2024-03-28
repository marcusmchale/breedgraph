import logging
from neo4j import AsyncGraphDatabase
from src.breedgraph.config import get_bolt_url, get_graphdb_auth, DATABASE_NAME

from neo4j import AsyncDriver

logger = logging.getLogger(__name__)


class DriverHolder:
    driver = None

    def __init__(self):
        pass


def get_driver() -> AsyncDriver:
    if not DriverHolder.driver:
        logger.info("Start neo4j driver connection")
        DriverHolder.driver = AsyncGraphDatabase.driver(
            get_bolt_url(),
            auth=get_graphdb_auth(),
            #database=DATABASE_NAME,
            connection_timeout=5,
            connection_acquisition_timeout=5,
            max_transaction_retry_time=5
        )
    return DriverHolder.driver

# todo currently not closing the driver, consider implementing a shutdown script and handling this there
