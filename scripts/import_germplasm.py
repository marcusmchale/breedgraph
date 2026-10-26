#!/usr/bin/env python3
"""
Loads germplasm entries and the relationships between them, once, after the site's first account is set up
(docs/deployment.md): released to the public, controlled by the team given, and written by the user given, all or
nothing.

The user must have write access to the team. A team's creator has admin access to it, but not write: in BreedView,
Access control, Teams, choose Set Affiliation on the team, and Write, which is approved at once for its admin.

From a checkout of the release, with the API's venv and environment loaded:

    python scripts/import_germplasm.py -e germplasm.json -r relationships.json -u <user id> -t <team id>

The entries are a JSON list of {"slug", "name"}, with any of "synonyms" (a list), "description" and "reproduction"
(CLONAL, SEXUAL or APOMIXIS); the slugs name them in the relationships, a list of {"source", "target", "sourceType"},
the target derived from the source, by SEED, TISSUE, MATERNAL, PATERNAL or UNKNOWN. Names must be new to the database,
so a second run is refused, writing nothing.
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

parser = argparse.ArgumentParser(description='Load germplasm entries and their relationships, once')
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

    unknown = sorted({rel[end] for rel in relationships for end in ('source', 'target')} - set(entries_map))
    if unknown:
        print(f"The relationships name entries the entries file doesn't have: {', '.join(unknown)}", file=sys.stderr)
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
        print(f"Loaded {len(entries_map)} germplasm entries and {len(relationships)} relationships")

    except json.JSONDecodeError as e:
        print("Error:", e)
        print("Line:", e.lineno, "Column:", e.colno)
    except Exception as e:
        # the application's logging goes to its log files, so the reason is printed too, and nothing was written
        logger.error(f"loading failed: {e}")
        print(f"Loading failed, and nothing was written: {e}", file=sys.stderr)
        if 'write affiliations' in str(e):
            print(
                "Give the user write access to the team first: in BreedView, Access control, Teams, choose Set "
                "Affiliation on the team, and Write",
                file=sys.stderr
            )
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