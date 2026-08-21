#!/usr/bin/env python3
"""
Initial data setup script for BreedGraph deployment.
This should be run once to load germplasm data.

Requires user_id and team_id to be supplied as arguments to the script for access control.
User_id must have write access to team_id.

"""
import argparse
import asyncio
import sys

from pathlib import Path
import json

from breedgraph.domain.model import ReadRelease
from breedgraph.domain.model.germplasm import GermplasmRelationship, GermplasmInput, GermplasmStored, GermplasmSourceType

import logging
logger = logging.getLogger(__name__)



from breedgraph.adapters.neo4j.unit_of_work import Neo4jUnitOfWorkFactory
from breedgraph.adapters.neo4j.driver import Neo4jAsyncDriver

parser = argparse.ArgumentParser(description='Short sample app')
parser.add_argument('-e', '--entries_json', action="store", dest='entries_json', required=True)
parser.add_argument('-r', '--relationships_json', action="store", dest='relationships_json', required=True)
parser.add_argument('-u', '--user_id', action="store", dest='user_id', required=True, type=int)
parser.add_argument('-t', '--team_id', action="store", dest='team_id', required=True, type=int)

args = parser.parse_args()

async def main():
    logger.info("Starting to load germplasm...")
    driver = None

    try:
        with open(Path(args.entries_json)) as f:
            entries = json.load(f)
            entries_map = {entry.pop("slug"): GermplasmInput(**entry) for entry in entries}
    except json.JSONDecodeError as e:
        print("Error parsing entries file:", e)
        print("Line:", e.lineno, "Column:", e.colno)
        sys.exit(1)

    try:
        with open(Path(args.relationships_json)) as f:
            relationships = json.load(f)

    except json.JSONDecodeError as e:
        print("Error parsing relationships file:", e)
        print("Line:", e.lineno, "Column:", e.colno)
        sys.exit(1)

    try:
        logger.info("Build neo4j driver")
        driver = Neo4jAsyncDriver()
        uow_factory = Neo4jUnitOfWorkFactory(driver)

        async with uow_factory.get_uow(
                user_id=args.user_id,
                write_team=args.team_id,
                release=ReadRelease.PUBLIC
        ) as uow:

            for slug, entry in entries_map.items():

                entries_map[slug] = await uow.germplasm.create_entry(entry)

            for i, rel in enumerate(relationships):
                source_entry = entries_map[rel.pop('source')]
                target_entry = entries_map[rel.pop('target')]
                source_type = GermplasmSourceType(rel.pop('sourceType'))
                relationships[i] = GermplasmRelationship(
                    source_id = source_entry.id,
                    sink_id = target_entry.id,
                    source_type=source_type
                )
            await uow.germplasm.create_relationships(relationships)
            await uow.commit()
        logger.info("Germplasm loaded successfully!")

    except json.JSONDecodeError as e:
        print("Error:", e)
        print("Line:", e.lineno, "Column:", e.colno)
    except Exception as e:
        logger.error(f"loading failed: {e}")
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