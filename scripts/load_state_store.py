#!/usr/bin/env python3
"""
Refresh the read models in the state store (Redis) from the database: on first setup, after restoring a dump or
a Redis shutdown, or after writing to the database outside the API, e.g. with a script.

Each read model is rebuilt whole and swapped in, so this is safe on a running instance: it touches nothing else
in Redis (submissions, analyses, files). Without --models, every read model is refreshed.

    python scripts/load_state_store.py                    # all read models
    python scripts/load_state_store.py --models countries ontology   # just these
"""
import argparse
import sys
import asyncio

from breedgraph.adapters.redis.read_models import RedisReadModels
from breedgraph.adapters.neo4j.driver import Neo4jAsyncDriver

import logging
logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
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


async def main(names: list[str] | None) -> bool:
    driver = Neo4jAsyncDriver()
    read_models = None
    try:
        read_models = await RedisReadModels.create(driver=driver)
        await read_models.refresh(names)
        logger.info("Read models refreshed")
        return True
    except Exception as e:
        logger.error(f"Refreshing the read models failed: {e}")
        return False
    finally:
        if read_models is not None:
            await read_models.close()
        await driver.close()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Refresh the read models in the state store from the database")
    parser.add_argument(
        '--models', nargs='+', choices=RedisReadModels.names, metavar='NAME',
        help=f"refresh only these read models, of: {', '.join(RedisReadModels.names)}"
    )
    if not asyncio.run(main(parser.parse_args().models)):
        sys.exit(1)
