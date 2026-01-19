#!/usr/bin/env python3
"""
Run this after setting up initial data on first setup, or after redis shutdown
"""
import sys
import asyncio
from pathlib import Path
import redis.asyncio as redis



# Add src to path so we can import our modules
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.breedgraph.adapters.redis.load_data import RedisLoader
from src.breedgraph.adapters.neo4j.driver import Neo4jAsyncDriver

from src.breedgraph.config import get_redis_host_and_port

import logging
logger = logging.getLogger(__name__)

async def is_redis_empty(connection):
    cursor = 0
    while True:
        cursor, keys = await connection.scan(cursor=cursor)
        if keys:
            return False  # Found some keys, Redis is not empty
        if cursor == 0:
            break
    return True  # No keys found, Redis is empty


async def main():
    logger.info("Starting state store setup...")

    connection = None
    driver = None

    try:
        logger.info("Get connection to redis")
        host, port = get_redis_host_and_port()
        connection = await redis.Redis(host=host, port=port, db=0)
        logger.info(f"Ping redis successful: {await connection.ping()}")

        assert await is_redis_empty(connection), "Redis is not empty, aborting!"

        logger.info("Build neo4j driver")
        driver = Neo4jAsyncDriver()

        logger.info("Starting to load redis")
        loader = RedisLoader(connection, driver)
        await loader.load_read_model()

        logger.info("State store setup completed successfully!")

    except Exception as e:
        logger.error(f"State store setup failed: {e}")
        sys.exit(1)

    finally:
        # Explicit cleanup of async resources BEFORE event loop closes
        if connection is not None:
            try:
                logger.debug("Closing Redis connection")
                await connection.aclose()
            except Exception as e:
                logger.warning(f"Error closing Redis connection: {e}")

        if driver is not None:
            try:
                logger.debug("Closing Neo4j driver")
                await driver.close()
            except Exception as e:
                logger.warning(f"Error closing Neo4j driver: {e}")


if __name__ == "__main__":
    asyncio.run(main())