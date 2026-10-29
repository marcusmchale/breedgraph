#!/usr/bin/env python3
"""
Seeds the standard licences, CC BY 4.0 and CC0 1.0, into a database set up before they were part of setting up
(docs/upgrading.md), as scripts/setup_initial_data.py seeds them into an empty one: fixed legal references, which
everyone can read and no one can change (docs/licences.md §6). It creates only what is missing, so it can be run again.
The ontology's next version then takes CC BY 4.0, unless an ontology admin names another.

From a checkout of the release, with the API's venv and environment loaded, after scripts/apply_schema.py:

    python scripts/seed_licences.py
"""
import asyncio
import logging
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from breedgraph.adapters.neo4j.driver import Neo4jAsyncDriver
from breedgraph.adapters.neo4j.unit_of_work import Neo4jUnitOfWorkFactory
from breedgraph.config.logging import log_to_console
from breedgraph.service_layer.application.licence_seed import seed_licences, STANDARD_LICENCES

logger = logging.getLogger(__name__)


async def main() -> int:
    driver = Neo4jAsyncDriver()
    try:
        uow_factory = Neo4jUnitOfWorkFactory(driver)
        async with uow_factory.get_uow() as uow:
            system_account = await uow.repositories.accounts.get(name='system')
        if system_account is None:
            logger.error("No system account: set the database up with scripts/setup_initial_data.py")
            return 1
        async with uow_factory.get_uow(user_id=system_account.user.id) as uow:
            ids = await seed_licences(uow.repositories.references)
            await uow.commit()
        for licence in STANDARD_LICENCES:
            logger.info(f"{licence.description}: reference {ids[licence.seed_key]}")
        return 0
    finally:
        await driver.close()


if __name__ == '__main__':
    log_to_console()
    sys.exit(asyncio.run(main()))
