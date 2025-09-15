#!/usr/bin/env python3
"""
Initial data setup script for BreedGraph deployment.
This should be run once during initial application deployment.
"""
import asyncio
import sys

from datetime import datetime
from pathlib import Path

# Add src to path so we can import our modules
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.breedgraph.domain.model.accounts import OntologyRole
from src.breedgraph.domain.model.ontology.location_type import LocationTypeInput, LocationTypeStored, LocationTypeOutput
from src.breedgraph.domain.model.ontology.version import Version

from src.breedgraph.service_layer.infrastructure.unit_of_work import AbstractUnitOfWork
from src.breedgraph.adapters.neo4j.unit_of_work import Neo4jUnitOfWork

from src.breedgraph.domain.model.accounts import AccountInput, UserInput

from src.breedgraph.config import MAIL_USERNAME, MAIL_HOST

import logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

async def create_initial_ontology_entries(uow: AbstractUnitOfWork = Neo4jUnitOfWork()):
    """Create essential ontology entries needed for the application."""
    # first create system account
    system_account_id = None
    async with uow.get_uow() as uow_holder:
        # Check if any records exist in the db, if so then stop now
        # This is a safeguard against running this script unintentionally
        logger.info("Checking if database is empty...")
        if not await uow_holder.db_is_empty():
            raise Exception("Database is not empty, aborting initial data setup...")

        # create system user
        logger.info("Creating system account...")
        system_account = await uow_holder.repositories.accounts.create(
            AccountInput(
                user = UserInput(
                    name='system',
                    fullname='system user',
                    email=f'{MAIL_USERNAME}@{MAIL_HOST}',
                    password_hash="",
                    ontology_role=OntologyRole('admin')
                )
            )
        )
        # so we can keep this in the same transaction, update the ontology role and user id manually
        # rather than starting a new uow
        uow_holder.ontology.role = system_account.user.ontology_role
        uow_holder.ontology.user_id = system_account.user.id
        # Create initial Ontology version
        await uow_holder.ontology.commit_version(
            version_change=None,
            comment="Initial version"
        )
        logger.info("Creating Country LocationType...")
        country_type_input = LocationTypeInput(
            name='Country',
            description='Country and three digit code according to ISO 3166-1 alpha-3'
        )
        await uow_holder.ontology.create_entry(
            entry=country_type_input
        )
        await uow_holder.commit()
        logger.info("Initial ontology setup completed successfully")


async def main():
    """Main setup function."""
    logger.info("Starting initial data setup...")

    try:
        await create_initial_ontology_entries()
        logger.info("Initial data setup completed successfully!")

    except Exception as e:
        logger.error(f"Setup failed: {e}")
        sys.exit(1)


if __name__ == "__main__":
    asyncio.run(main())