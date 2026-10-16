#!/usr/bin/env python3
"""
Rehearse the BreedCAFS migration on the synthetic test database (scripts/build_test_database.py), as it will run on a
copy of production (src/breedcafs_migration/RUNBOOK.md): on a database that already has accounts, teams, an ontology and
germplasm.

It sets up what the runbook expects to exist before the migration (§1), as the test database's admin account:
  - a root team whose team tree has declared a legal entity, the data controller of the Persons,
    of which the admin is a heritable admin (as creator of the team tree) and a writer (to load the germplasm);
  - the production germplasm (src/data/germplasm), as scripts/import_germplasm.py loads it, unless --no-germplasm.
It then runs the runbook's own commands (python -m breedcafs_migration.main): bundle the data directory and unbundle
it into --rehearsal-dir, as it will be carried to the server, then bootstrap, migrate and validate there, and exits
with the validation's status. Every step finds what an earlier run created, so it can be run again: an existing
rehearsal directory is used as it is, with its mapping files.

The result holds BreedCAFS data, including Person data: dump it under its own name and keep it private.
Never dump it as the public test database.

    set -a; . instance/breedgraph.env; . instance/private.breedgraph.env; set +a
    python scripts/rehearse_migration.py --manifest instance/neo4j_archive/test_databases/test_database.manifest.json 2>&1 | tee rehearsal.log
"""
import argparse
import asyncio
import json
import os
import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(ROOT / 'src'))

from breedgraph import config
from breedgraph.adapters.neo4j.driver import Neo4jAsyncDriver
from breedgraph.adapters.neo4j.unit_of_work import Neo4jUnitOfWorkFactory
from breedgraph.domain.model import ReadRelease
from breedgraph.domain.model.germplasm import GermplasmInput, GermplasmRelationship, GermplasmSourceType
from breedgraph.domain.model.controls import Access
from breedgraph.domain.model.team_trees import TeamInput

import logging
logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
logger = logging.getLogger(__name__)

REHEARSAL_TEAM = "BreedCAFS Rehearsal University"
LEGAL_NAME = "BreedCAFS Rehearsal University (not a real organisation)"
PRIVACY_CONTACT = "privacy@example.org"

DATA_DIR = ROOT / 'src' / 'data'


async def get_or_create_rehearsal_team(uow_factory: Neo4jUnitOfWorkFactory, admin_id: int) -> int:
    """The root team of a team tree with a declared legal entity, created by the admin, who can also write to it"""
    team_id = await create_rehearsal_team(uow_factory, admin_id)
    async with uow_factory.get_uow(user_id=admin_id) as uow:
        team_tree = await uow.repositories.team_trees.get(team_id=team_id)
        if admin_id not in team_tree.get_affiliates(team_id, Access.WRITE, inheritance=False):
            logger.info("Affiliating the admin with WRITE access")
            team_tree.request_affiliation(agent_id=admin_id, user_id=admin_id, team_id=team_id, access=Access.WRITE)
            team_tree.authorise_affiliation(agent_id=admin_id, user_id=admin_id, team_id=team_id, access=Access.WRITE)
            await uow.commit()
    return team_id


async def create_rehearsal_team(uow_factory: Neo4jUnitOfWorkFactory, admin_id: int) -> int:
    async with uow_factory.get_uow(user_id=admin_id) as uow:
        async for team_tree in uow.repositories.team_trees.get_all():
            if team_tree.root.name == REHEARSAL_TEAM:
                logger.info(f"Using the existing {REHEARSAL_TEAM} team {team_tree.get_root_id()}")
                return team_tree.get_root_id()

        if config.DATA_PROCESSING_TERMS_VERSION is None:
            raise RuntimeError("DATA_PROCESSING_TERMS_VERSION is not set, so a legal entity cannot be declared")
        logger.info(f"Creating the {REHEARSAL_TEAM} team, with a legal entity")
        team_tree = await uow.repositories.team_trees.create(TeamInput(name=REHEARSAL_TEAM, fullname=REHEARSAL_TEAM))
        team_tree.declare_legal_entity(
            agent_id=admin_id,
            team_id=team_tree.get_root_id(),
            legal_name=LEGAL_NAME,
            privacy_contact=PRIVACY_CONTACT,
            terms_version=config.DATA_PROCESSING_TERMS_VERSION,
            current_terms_version=config.DATA_PROCESSING_TERMS_VERSION
        )
        team_id = team_tree.get_root_id()
        await uow.commit()
    return team_id


async def import_germplasm(uow_factory: Neo4jUnitOfWorkFactory, admin_id: int, team_id: int, germplasm_dir: Path) -> None:
    """The production germplasm, as scripts/import_germplasm.py loads it, unless already loaded"""
    entries = json.loads((germplasm_dir / 'germplasm.json').read_text())
    relationships = json.loads((germplasm_dir / 'relationships.json').read_text())
    async with uow_factory.get_uow(user_id=admin_id, write_team=team_id, release=ReadRelease.PUBLIC) as uow:
        existing = [entry async for entry in uow.germplasm.get_entries(names=[entries[0]['name']])]
        if existing:
            logger.info("The germplasm is already loaded")
            return
        logger.info(f"Loading {len(entries)} germplasm entries")
        stored = {}
        for entry in entries:
            slug = entry.pop('slug')
            stored[slug] = await uow.germplasm.create_entry(GermplasmInput(**entry))
        await uow.germplasm.create_relationships([
            GermplasmRelationship(
                source_id=stored[rel['source']].id,
                sink_id=stored[rel['target']].id,
                source_type=GermplasmSourceType(rel['sourceType'])
            )
            for rel in relationships
        ])
        await uow.commit()


async def prepare(admin_id: int, germplasm_dir: Path | None) -> int:
    driver = Neo4jAsyncDriver()
    try:
        uow_factory = Neo4jUnitOfWorkFactory(driver)
        team_id = await get_or_create_rehearsal_team(uow_factory, admin_id)
        if germplasm_dir is not None:
            await import_germplasm(uow_factory, admin_id, team_id, germplasm_dir)
        return team_id
    finally:
        await driver.close()


def run_step(env: dict, step: str, *args: str) -> subprocess.CompletedProcess:
    """A runbook step, with its output passed through as it runs and also returned"""
    logger.info(f"Running: breedcafs_migration.main {step} {' '.join(args)}")
    output = []
    with subprocess.Popen(
            [sys.executable, '-m', 'breedcafs_migration.main', step, *args],
            env=env, cwd=ROOT, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True
    ) as process:
        for line in process.stdout:
            print(line, end='', flush=True)
            output.append(line)
    return subprocess.CompletedProcess(process.args, process.returncode, stdout=''.join(output))


def main() -> int:
    parser = argparse.ArgumentParser(description="Rehearse the BreedCAFS migration on the test database")
    parser.add_argument('--manifest', type=Path, required=True, help="the test database's manifest, for its admin account")
    parser.add_argument(
        '--data-dir', type=Path, default=DATA_DIR / 'breedcafs_migration',
        help="the BreedCAFS data directory (default src/data/breedcafs_migration)"
    )
    parser.add_argument(
        '--rehearsal-dir', type=Path, default=DATA_DIR / 'breedcafs_migration_rehearsal',
        help="where the rehearsal's copy of the data and its mapping files go (default src/data/breedcafs_migration_rehearsal)"
    )
    parser.add_argument('--germplasm-dir', type=Path, default=DATA_DIR / 'germplasm', help="the production germplasm")
    parser.add_argument('--no-germplasm', action='store_true', help="don't load the production germplasm")
    args = parser.parse_args()

    admin_id = json.loads(args.manifest.read_text())['accounts']['admin']['user_id']
    germplasm_dir = None if args.no_germplasm else args.germplasm_dir
    if germplasm_dir is not None and not (germplasm_dir / 'germplasm.json').is_file():
        parser.error(f"No germplasm.json in {germplasm_dir}; give --germplasm-dir, or --no-germplasm")

    team_id = asyncio.run(prepare(admin_id, germplasm_dir))

    if args.rehearsal_dir.exists():
        logger.info(f"Using the existing rehearsal data directory {args.rehearsal_dir}, with its mapping files")
    else:
        # the bundle holds Person data: it is kept only while it is unpacked
        archive = args.rehearsal_dir.with_name(args.rehearsal_dir.name + '.tar.gz')
        try:
            for step in (
                    ('bundle', '--data-dir', str(args.data_dir), '--out', str(archive)),
                    ('unbundle', str(archive), '--data-dir', str(args.rehearsal_dir))
            ):
                if run_step(dict(os.environ), *step).returncode != 0:
                    logger.error(f"The {step[0]} step failed")
                    return 2
        finally:
            archive.unlink(missing_ok=True)

    env = {
        **os.environ,
        'BREEDCAFS_ADMIN_USER_ID': str(admin_id),
        'BREEDCAFS_PARENT_TEAM_ID': str(team_id),
        'BREEDCAFS_DATA_DIR': str(args.rehearsal_dir.resolve()),
    }
    process = run_step(env, 'bootstrap')
    found = re.search(r"Migration user id: (\d+), team id: (\d+)", process.stdout)
    if process.returncode != 0 or found is None:
        logger.error("The bootstrap failed")
        return process.returncode or 1
    ids = ['--user-id', found.group(1), '--team-id', found.group(2)]

    process = run_step(env, 'migrate', *ids)
    if process.returncode != 0:
        logger.error("The migration failed; fix the cause and run this again, as the runbook says")
        return process.returncode

    process = run_step(env, 'validate', *ids)
    logger.info(
        f"Validation {'passed' if process.returncode == 0 else 'FAILED'}; "
        f"report at {args.rehearsal_dir / 'validation_report.md'}"
    )
    logger.info(f"Migration user {found.group(1)}, team {found.group(2)}, under {REHEARSAL_TEAM} ({team_id})")
    return process.returncode


if __name__ == '__main__':
    sys.exit(main())
