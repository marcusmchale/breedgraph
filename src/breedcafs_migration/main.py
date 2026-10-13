"""
BreedCAFS migration (README.md).

    python -m breedcafs_migration.main bootstrap
        Create the migration user and team (BREEDCAFS_ADMIN_USER_ID, BREEDCAFS_PARENT_TEAM_ID) and print their ids.
    python -m breedcafs_migration.main migrate --user-id <id> --team-id <id>
        Run the migration phases as the migration user, with the migration team as write team.
    python -m breedcafs_migration.main validate --user-id <id> --team-id <id>
        Check what was migrated against the extracted and mapping files; exits with 3 if a check fails.
"""
import argparse
import asyncio
import sys

from breedgraph.adapters.neo4j.driver import Neo4jAsyncDriver
from breedgraph.adapters.neo4j.unit_of_work import Neo4jUnitOfWorkFactory

from breedcafs_migration.bootstrap import setup_breedcafs_migration_account, MigrationContext, MigrationSettingsError
from breedcafs_migration.ontology import prepare_breedcafs_ontology
from breedcafs_migration.germplasm import prepare_breedcafs_germplasm, GermplasmNameConflict
from breedcafs_migration.locations import prepare_breedcafs_locations
from breedcafs_migration.layouts import prepare_breedcafs_layouts
from breedcafs_migration.units import prepare_breedcafs_units
from breedcafs_migration.programs import prepare_breedcafs_programs
from breedcafs_migration.datasets import prepare_breedcafs_datasets
from breedcafs_migration.curves import prepare_breedcafs_curves
from breedcafs_migration.persons import prepare_breedcafs_persons
from breedcafs_migration.validate import validate_breedcafs_migration

import logging
logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
logger = logging.getLogger(__name__)


async def bootstrap(uow_factory: Neo4jUnitOfWorkFactory) -> None:
    context = await setup_breedcafs_migration_account(uow_factory=uow_factory)
    print(f"Migration user id: {context.user_id}, team id: {context.team_id}")


async def migrate(uow_factory: Neo4jUnitOfWorkFactory, context: MigrationContext) -> None:
    logger.info("Prepare ontology")
    ontology_ids = await prepare_breedcafs_ontology(uow_factory=uow_factory, user_id=context.user_id)
    logger.info("Prepare germplasm")
    germplasm_ids = await prepare_breedcafs_germplasm(uow_factory=uow_factory, context=context)
    logger.info("Prepare locations")
    location_ids = await prepare_breedcafs_locations(
        uow_factory=uow_factory, context=context, location_types=ontology_ids.location_types
    )
    logger.info("Prepare layouts")
    layout_ids = await prepare_breedcafs_layouts(
        uow_factory=uow_factory, context=context,
        layout_types=ontology_ids.layout_types, field_locations=location_ids.fields
    )
    logger.info("Prepare units")
    unit_ids = await prepare_breedcafs_units(
        uow_factory=uow_factory, context=context, subjects=ontology_ids.subjects,
        germplasm=germplasm_ids.varieties, locations=location_ids, layouts=layout_ids
    )
    logger.info("Prepare the program, trials and studies")
    program_ids = await prepare_breedcafs_programs(
        uow_factory=uow_factory, context=context, record_group_types=ontology_ids.record_group_types
    )
    logger.info("Prepare datasets")
    dataset_ids = await prepare_breedcafs_datasets(
        uow_factory=uow_factory, context=context, ontology=ontology_ids, programs=program_ids, units=unit_ids.units
    )
    logger.info("Prepare curves")
    curve_ids = await prepare_breedcafs_curves(
        uow_factory=uow_factory, context=context, ontology=ontology_ids, programs=program_ids,
        units=unit_ids.units, datasets=dataset_ids
    )
    logger.info("Prepare Persons and dataset contributors")
    await prepare_breedcafs_persons(
        uow_factory=uow_factory, context=context, ontology=ontology_ids, datasets=dataset_ids, curves=curve_ids
    )


async def main(args: argparse.Namespace) -> bool:
    driver = Neo4jAsyncDriver()
    try:
        uow_factory = Neo4jUnitOfWorkFactory(driver=driver)
        if args.step == 'bootstrap':
            await bootstrap(uow_factory)
        elif args.step == 'migrate':
            await migrate(uow_factory, MigrationContext(user_id=args.user_id, team_id=args.team_id))
        else:
            validation = await validate_breedcafs_migration(uow_factory, MigrationContext(user_id=args.user_id, team_id=args.team_id))
            return validation.passed
        return True
    finally:
        await driver.close()


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Migrate BreedCAFS data into BreedGraph")
    steps = parser.add_subparsers(dest='step', required=True)
    steps.add_parser('bootstrap', help="Create the migration user and team")
    for step, description in (('migrate', "Run the migration phases"), ('validate', "Check the migrated data")):
        step_parser = steps.add_parser(step, help=description)
        step_parser.add_argument('--user-id', type=int, required=True, help="The migration user")
        step_parser.add_argument('--team-id', type=int, required=True, help="The migration team")
    return parser.parse_args()


if __name__ == "__main__":
    try:
        if not asyncio.run(main(parse_args())):
            sys.exit(3)
    except (MigrationSettingsError, GermplasmNameConflict) as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(2)
    except Exception:
        logger.exception("Migration failed")
        sys.exit(1)
