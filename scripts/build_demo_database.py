#!/usr/bin/env python3
"""
Build the demonstration database on an empty Neo4j and Redis: fictional winter wheat trials in Ireland, in plain
English, for the University's data protection and legal offices and for showing BreedGraph to outside users
(tests/breedgraph/scenarios/demo/, docs/demo-database.md). Build it into throwaway services, so its dump comes from a
fresh store and holds nothing written before:

    set -a; . instance/breedgraph.env; . instance/private.breedgraph.env; set +a
    SCRATCH=<dir> scripts/scratch_services.sh build instance/neo4j_archive/demo_databases/demo_database.dump -- \\
        .venv/bin/python scripts/build_demo_database.py \\
            --manifest instance/neo4j_archive/demo_databases/demo_database.manifest.json \\
            --password-file instance/private.demo_passwords.json

Writes a private manifest (readable by its owner only): the accounts with their passwords, every entity's id by the
story's key, and what each of the guide's workflows starts from. The stored files are copied beside it (<name>_files),
to restore with the dump, and the files the guide uploads are written beside it too (<name>_uploads).
"""
import argparse
import asyncio
import json
import secrets
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(ROOT / 'src'))
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(Path(__file__).parent))

from breedgraph.config import FILE_STORAGE_PATH, PRIVACY_NOTICE_PATH, get_bolt_url
from breedgraph.service_layer.application.terms_of_use import load_legal_text

from database_builds import (
    git_commit, require_environment, empty_database, add_names, files_dir_for, copy_files, write_manifest
)
import check_person_controllers
import check_study_licences

from tests.breedgraph.scenarios.demo.builder import DemoScenarioBuilder
from tests.breedgraph.scenarios.demo.manifest import demo_manifest, uploads
from tests.breedgraph.scenarios.demo.story import ACCOUNTS

import logging
logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
logging.getLogger('faker').setLevel(logging.WARNING)
logger = logging.getLogger(__name__)

DEVELOPMENT_BOLT_PORT = '7687'


def passwords_from(args) -> dict[str, str]:
    if args.password_file:
        given = json.loads(Path(args.password_file).read_text())
        missing = sorted(set(ACCOUNTS) - set(given))
        if missing:
            raise SystemExit(f"{args.password_file} has no password for {', '.join(missing)}")
        return {key: given[key] for key in ACCOUNTS}
    if args.password:
        logger.warning("A password on the command line is kept in the shell's history and shown by ps: prefer --password-file")
        return {key: args.password for key in ACCOUNTS}
    # generated: written only to the manifest
    return {key: secrets.token_urlsafe(12) for key in ACCOUNTS}


async def build(manifest_path: Path, passwords: dict[str, str]):
    require_environment()
    files_dir = files_dir_for(manifest_path)
    uploads_dir = manifest_path.parent / f"{manifest_path.stem.removesuffix('.manifest')}_uploads"
    built_at = datetime.now(timezone.utc).isoformat()

    async with empty_database() as services:
        logger.info("Building the demonstration story")
        scenario = await DemoScenarioBuilder(
            services.uow_factory,
            services.state_store,
            passwords,
            archival_service=services.archival_service(),
            file_storage_path=FILE_STORAGE_PATH,
            # the accounts consented to the privacy notice served now
            privacy_notice_hash=load_legal_text(PRIVACY_NOTICE_PATH).content_hash
        ).build()
        # the build created a country without the message bus
        await services.read_models.refresh()
        contents = demo_manifest(scenario, passwords, files_dir, uploads_dir, built_at, git_commit())
        await add_names(services.driver, contents)

    # the checks a deployment runs: every licence released widely enough, every Person controlled and not public
    for check in (check_study_licences, check_person_controllers):
        if await check.main():
            raise RuntimeError(f"{check.__name__} found problems in the build (above)")

    copy_files([file_id for file_id, _, _ in scenario.files.values()], files_dir)
    uploads_dir.mkdir(parents=True, exist_ok=True)
    for path, content in uploads(uploads_dir).items():
        path.write_bytes(content)
    write_manifest(manifest_path, contents, private=True)

    logger.info(f"Built {len(contents['entities'])} entities; manifest at {manifest_path}, files in {files_dir}, "
                f"uploads in {uploads_dir}")


def main():
    parser = argparse.ArgumentParser(description=__doc__.split('\n\n')[0], formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument('--manifest', type=Path, required=True, help="where to write the manifest (JSON), which holds the passwords")
    passwords = parser.add_mutually_exclusive_group()
    passwords.add_argument('--password-file', help="a JSON object of each account's password by its username (dara, bridget, ...)")
    passwords.add_argument('--password', help="one password for every account (seen in the shell's history)")
    passwords.add_argument('--generate', action='store_true', help="random passwords, written to the manifest only (the default)")
    parser.add_argument(
        '--allow-development-database', action='store_true',
        help="build even on the development Neo4j's port, whose store holds what was written before (see --help)"
    )
    args = parser.parse_args()
    if args.manifest.exists():
        parser.error(f"{args.manifest} exists: remove it or choose another path")
    if get_bolt_url().rsplit(':', 1)[-1] == DEVELOPMENT_BOLT_PORT and not args.allow_development_database:
        parser.error(
            "Neo4j is the development instance (port 7687): build into throwaway services from a fresh store "
            "(scripts/scratch_services.sh build), or pass --allow-development-database for a build not to share"
        )
    try:
        asyncio.run(build(args.manifest, passwords_from(args)))
    except Exception as e:
        logger.exception(f"Build failed: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
