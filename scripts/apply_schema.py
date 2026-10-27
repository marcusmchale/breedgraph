#!/usr/bin/env python3
"""
Create any constraints and indexes the database is missing (see cypher/infrastructure), without touching its data.
Run it after deploying a version that adds constraints or indexes: setup_initial_data.py only runs on an empty database.
Uniqueness constraints fail on data that breaks them; the failures are logged and the script exits non-zero.
"""
import asyncio
import sys

from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))
sys.path.insert(0, str(Path(__file__).parent))

from breedgraph.adapters.neo4j.driver import Neo4jAsyncDriver
from setup_initial_data import create_schema

import logging
from breedgraph.config.logging import log_to_console
logger = logging.getLogger(__name__)


async def main():
    driver = Neo4jAsyncDriver()
    try:
        async with driver.session() as session:
            succeeded = await create_schema(session)
    finally:
        await driver.close()
    if not succeeded:
        sys.exit(1)
    logger.info("Constraints and indexes are in place")


if __name__ == "__main__":
    log_to_console()
    asyncio.run(main())
