#!/usr/bin/env python3
"""
Erase a Person for a request made to the University, as the data controller, by someone who can't erase it in
BreedGraph themselves (docs/person.md §6): usually because they have no account linked to the record.
Confirm who is asking first. Erasing removes the Person's name, institution, teams and ORCID iD and its link to an
account, keeping an anonymous record number so research data stays attributed. It cannot be undone.

The erasure is written to the erasure log (PERSON_ERASURE_LOG_PATH), as erasures in BreedGraph are, so it is applied
again after restoring a backup.

Usage, with the instance env files sourced:  python scripts/erase_person.py <person id>
"""
import asyncio
import sys

from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from breedgraph.adapters.files import JsonLinesErasureLog
from breedgraph.adapters.neo4j.driver import Neo4jAsyncDriver
from breedgraph.adapters.neo4j.erasures import erase_person
from breedgraph.custom_exceptions import NoResultFoundError

import logging
logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
logger = logging.getLogger(__name__)


async def main(person_id: int) -> int:
    driver = Neo4jAsyncDriver()
    try:
        erased = await erase_person(driver, JsonLinesErasureLog(), person_id)
    except NoResultFoundError as e:
        logger.error(str(e))
        return 1
    finally:
        await driver.close()
    if erased:
        logger.info(f"Erased Person {person_id}, and logged the erasure")
    else:
        logger.info(f"Person {person_id} was already erased")
    return 0


if __name__ == "__main__":
    if len(sys.argv) != 2 or not sys.argv[1].isdigit():
        sys.exit("Usage: python scripts/erase_person.py <person id>")
    sys.exit(asyncio.run(main(int(sys.argv[1]))))
