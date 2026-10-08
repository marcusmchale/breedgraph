#!/usr/bin/env python3
"""
Apply the Person erasure log to the database again.
Run after restoring a database backup, so Persons erased since the backup was taken stay erased.
The log is read from PERSON_ERASURE_LOG_PATH, or from the path given as the first argument.
"""
import asyncio
import sys

from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from breedgraph.adapters.files import JsonLinesErasureLog
from breedgraph.adapters.neo4j.driver import Neo4jAsyncDriver
from breedgraph.adapters.neo4j.erasures import apply_person_erasures

import logging
logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
logger = logging.getLogger(__name__)


async def main(log_path: str | None = None):
    erasure_log = JsonLinesErasureLog(log_path)
    if not erasure_log.path.exists():
        logger.error(f"Erasure log not found: {erasure_log.path}")
        sys.exit(1)

    entries = erasure_log.read()
    logger.info(f"Applying {len(entries)} logged erasures from {erasure_log.path}")
    driver = Neo4jAsyncDriver()
    try:
        erased = await apply_person_erasures(driver, entries)
    finally:
        await driver.close()
    logger.info(f"Erasures applied to {erased} Persons")


if __name__ == "__main__":
    asyncio.run(main(sys.argv[1] if len(sys.argv) > 1 else None))
