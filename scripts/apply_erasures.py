#!/usr/bin/env python3
"""
Apply the erasure log to the database again.
Run after restoring a database backup, so Persons erased and accounts deleted since the backup was taken stay that way.
The log is read from PERSON_ERASURE_LOG_PATH, or from the path given as the first argument.

Each entry is applied to the record with its id and creation time only, so a Person or account given the same id
since (after a restore rolled the id counter back, or in another database's dump) is left alone, and reported.
Entries without a creation time can't be matched to their record, so are skipped and reported.
The id counters are then advanced past the logged ids, so they are not issued again (docs/person.md §5).
"""
import asyncio
import sys

from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from breedgraph.adapters.files import JsonLinesErasureLog
from breedgraph.adapters.neo4j.driver import Neo4jAsyncDriver
from breedgraph.adapters.neo4j.erasures import replay_erasure_log

import logging
logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
logger = logging.getLogger(__name__)


async def main(log_path: str | None) -> int:
    erasure_log = JsonLinesErasureLog(log_path)
    if not erasure_log.path.exists():
        logger.error(f"Erasure log not found: {erasure_log.path}")
        return 1

    driver = Neo4jAsyncDriver()
    try:
        replay = await replay_erasure_log(driver, erasure_log)
    finally:
        await driver.close()
    logger.info(
        f"Applied {replay.entries} logged erasures and account deletions from {erasure_log.path}: "
        f"{replay.applied.persons} Persons erased, and {replay.applied.accounts} accounts deleted again"
    )
    if replay.applied.reissued_persons or replay.applied.reissued_accounts:
        logger.warning(
            f"Left alone, as their ids now belong to records created at another time than the logged ones: "
            f"Persons {list(replay.applied.reissued_persons)}, accounts {list(replay.applied.reissued_accounts)}"
        )
    if replay.untimed:
        logger.warning(f"Skipped {replay.untimed} entries without a creation time, which can't be matched to their record")
    if replay.counters:
        logger.info(f"Id counters advanced past the logged ids: {replay.counters}")
    return 0


if __name__ == "__main__":
    sys.exit(asyncio.run(main(sys.argv[1] if len(sys.argv) > 1 else None)))
