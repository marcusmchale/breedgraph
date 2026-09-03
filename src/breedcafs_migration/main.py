import asyncio
import sys

from breedgraph.adapters.neo4j.driver import Neo4jAsyncDriver
from breedgraph.adapters.neo4j.unit_of_work import Neo4jUnitOfWorkFactory, Neo4jUnitHolder
from breedcafs_migration.setup.breedcafs_driver import BreedCAFSAsyncDriver

from breedcafs_migration.bootstrap import setup_breedcafs_migration_account

from breedcafs_migration.ontology import prepare_breedcafs_ontology

import logging
logging.basicConfig(level=logging.DEBUG, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
logger = logging.getLogger(__name__)



async def main():
    logger.info("Starting BreedCAFS data migration...")

    breedgraph_driver = None
    breedcafs_driver = None

    try:
        logger.info("Build BreedGraph driver")
        breedgraph_driver = Neo4jAsyncDriver()

        logger.info("Build BreedCAFS driver")
        breedcafs_driver = BreedCAFSAsyncDriver()

        logger.info("Build BreedGraph UOW factory")
        breedgraph_uow_factory = Neo4jUnitOfWorkFactory(driver=breedgraph_driver)

        logger.info("Setup BreedCAFS migration account")
        user_id = await setup_breedcafs_migration_account(uow_factory=breedgraph_uow_factory)
        logger.info("Prepare Ontology")
        await prepare_breedcafs_ontology(uow_factory=breedgraph_uow_factory, user_id=user_id)




    except Exception as e:
        logger.error(f"Setup failed: {e}")
        sys.exit(1)

    finally:
        if breedcafs_driver is not None:
            try:
                logger.debug("Closing BreedGraph driver")
                await breedgraph_driver.close()
            except Exception as e:
                logger.warning(f"Error closing BreedGraph driver: {e}")

        if breedcafs_driver is not None:
            try:
                logger.debug("Closing BreedCAFS driver")
                await breedcafs_driver.close()
            except Exception as e:
                logger.warning(f"Error closing BreedCAFS driver: {e}")


if __name__ == "__main__":
    asyncio.run(main())