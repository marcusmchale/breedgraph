#!/usr/bin/env python3
"""
Initial data setup script for BreedGraph deployment.
This should be run once during initial application deployment.
"""
import asyncio
import sys

from pathlib import Path

from neo4j import AsyncTransaction, AsyncSession

# Add src to path so we can import our modules
sys.path.insert(0, str(Path(__file__).parent.parent))

from breedgraph.domain.model.accounts import OntologyRole
from breedgraph.domain.model.ontology import LocationTypeInput, VersionChange


from breedgraph.service_layer.infrastructure.unit_of_work import AbstractUnitOfWorkFactory
from breedgraph.adapters.neo4j.unit_of_work import Neo4jUnitOfWorkFactory
from breedgraph.adapters.neo4j.driver import Neo4jAsyncDriver

from breedgraph.domain.model.accounts import AccountInput, UserInput, AccountStored

from breedgraph.adapters.neo4j.cypher import queries

import logging
logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
logger = logging.getLogger(__name__)

async def ensure_empty_db(session: AsyncSession) -> None:
    logger.info("Checking if database is empty...")
    result = await session.run(queries['infrastructure']['is_empty'])
    is_empty = (await result.single(strict=True))["empty"]
    if not is_empty:
        raise Exception("Database is not empty, aborting setup...")

async def create_schema(session: AsyncSession) -> bool:
    """
    Create the constraints and indexes, each in its own transaction so that one failing does not undo the others.
    Every statement is IF NOT EXISTS, so this also brings an existing database up to date (scripts/apply_schema.py).
    Returns whether all of them were created or already existed.
    """
    logger.info("Creating constraints and indexes...")
    succeeded = True
    for name in ('create_constraints', 'create_indexes'):
        for statement in queries['infrastructure'][name].split(';'):
            statement = statement.strip()
            if not statement:
                continue
            try:
                logger.debug(f"Running: {statement}")
                await (await session.run(statement)).consume()
            except Exception as e:
                logger.error(f"Failed to run {statement}: {e}")
                succeeded = False
    return succeeded

async def create_system_account(uow: AbstractUnitOfWorkFactory) -> AccountStored:
    async with uow.get_uow() as uow_holder:
        logger.info("Creating system account...")
        system_account = await uow_holder.repositories.accounts.create(
            AccountInput(
                user=UserInput(
                    name='system',
                    fullname='system user',
                    email='',
                    password_hash='',
                    ontology_role=OntologyRole.ADMIN
                )
            )
        )
        await uow_holder.commit()
        return system_account

async def create_initial_ontology_entries(
    system_account: AccountStored,
    uow: AbstractUnitOfWorkFactory
):
    """Create essential ontology entries needed for the application."""
    async with uow.get_uow(user_id=system_account.user.id) as uow_holder:
        logger.info("Creating Country LocationType...")
        country_type_input = LocationTypeInput(
            name='Country',
            description='Country and three digit code according to ISO 3166-1 alpha-3'
        )
        await uow_holder.ontology.create_entry(
            entry=country_type_input
        )
        await uow_holder.ontology.commit_version(version_change=None, comment="Initial system commit")
        await uow_holder.commit()
        logger.info("Initial ontology setup completed successfully")


async def main():
    logger.info("Starting initial data setup...")

    driver = None

    try:
        logger.info("Build neo4j driver")
        driver = Neo4jAsyncDriver()
        async with driver.session() as session:
            await ensure_empty_db(session)
            await create_schema(session)

        logger.debug("Build uow holder")
        uow = Neo4jUnitOfWorkFactory(driver)
        system_account = await create_system_account(uow)
        await create_initial_ontology_entries(system_account, uow)
        logger.info("Initial data setup completed successfully!")

    except Exception as e:
        logger.error(f"Setup failed: {e}")
        sys.exit(1)

    finally:
        if driver is not None:
            try:
                logger.debug("Closing neo4j driver")
                await driver.close()
            except Exception as e:
                logger.warning(f"Error closing neo4j driver: {e}")


if __name__ == "__main__":
    asyncio.run(main())