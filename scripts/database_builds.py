"""
The steps the database build scripts share (scripts/build_test_database.py and scripts/build_demo_database.py): an
empty Neo4j and Redis set up as setup_initial_data.py would, without the message bus, and after the scenarios, the
names the app shows read back into the manifest and the stored files copied beside it.

Imported by those scripts, which put src/, the repository root and scripts/ on the import path first.
"""
import json
import os
import shutil
import subprocess
from asyncio import Queue
from contextlib import asynccontextmanager
from dataclasses import dataclass
from pathlib import Path
from typing import AsyncIterator, Iterable

import redis.asyncio as redis

from breedgraph.config import FILE_STORAGE_PATH, COUNTRY_CODES_PATH, get_redis_host_and_port
from breedgraph.domain.model.controls import ControlledModelLabel
from breedgraph.adapters.neo4j.driver import Neo4jAsyncDriver
from breedgraph.adapters.neo4j.unit_of_work import Neo4jUnitOfWorkFactory
from breedgraph.adapters.neo4j.services.file_archival_service import Neo4jFileArchivalService
from breedgraph.adapters.redis.read_models import RedisReadModels
from breedgraph.adapters.redis.state_store import RedisStateStore

from setup_initial_data import ensure_empty_db, create_schema, create_system_account, create_initial_ontology_entries
from load_state_store import is_redis_empty

import logging
logger = logging.getLogger(__name__)

ROOT = Path(__file__).parent.parent


def git_commit() -> str | None:
    try:
        return subprocess.run(
            ['git', 'rev-parse', 'HEAD'], cwd=ROOT, capture_output=True, text=True, check=True
        ).stdout.strip()
    except (OSError, subprocess.CalledProcessError):
        return None


def require_environment() -> None:
    if not FILE_STORAGE_PATH:
        raise RuntimeError("FILE_STORAGE_PATH is not set: load the instance environment first")
    if not Path(COUNTRY_CODES_PATH).is_file():
        # the scenario's location trees are countries from this file, which the state store holds
        raise RuntimeError(f"No country codes at COUNTRY_CODES_PATH ({COUNTRY_CODES_PATH}), e.g. src/data/country_codes.csv")


@dataclass
class BuildServices:
    driver: Neo4jAsyncDriver
    connection: redis.Redis
    uow_factory: Neo4jUnitOfWorkFactory
    read_models: RedisReadModels
    state_store: RedisStateStore

    def archival_service(self) -> Neo4jFileArchivalService:
        """Records stored files for archival, as uploads are"""
        return Neo4jFileArchivalService(driver=self.driver, queue=Queue())


@asynccontextmanager
async def empty_database() -> AsyncIterator[BuildServices]:
    """
    Set up an empty Neo4j and Redis as setup_initial_data.py would: the schema, the system account and the seeded
    ontology entries, with the read models loaded. Refuses a database or state store that isn't empty.
    """
    driver = Neo4jAsyncDriver()
    host, port = get_redis_host_and_port()
    connection = redis.Redis(host=host, port=port, db=0)
    try:
        async with driver.session() as session:
            await ensure_empty_db(session)
        if not await is_redis_empty(connection):
            raise RuntimeError("Redis is not empty, aborting: the state store must be built with the database")

        async with driver.session() as session:
            if not await create_schema(session):
                raise RuntimeError("Constraints or indexes could not be created")
        # no message bus: account events would send email, and the scenarios write what uploads would
        uow_factory = Neo4jUnitOfWorkFactory(driver)
        system_account = await create_system_account(uow_factory)
        await create_initial_ontology_entries(system_account, uow_factory)

        logger.info("Loading the state store")
        read_models = await RedisReadModels.create(driver=driver, connection=connection)
        await read_models.refresh()
        yield BuildServices(
            driver=driver,
            connection=connection,
            uow_factory=uow_factory,
            read_models=read_models,
            state_store=RedisStateStore(connection)
        )
    finally:
        await connection.aclose()
        await driver.close()


async def add_names(driver: Neo4jAsyncDriver, contents: dict) -> None:
    """
    Add each entity's and team's name, as the app shows it, from the database: a reference's description, and none for
    a dataset, which is known by its study and concept. Every id must be found under its label.
    """
    by_label: dict[str, dict[int, dict]] = {}
    for entity in contents['entities'].values():
        # the label is checked against the model's labels before it goes into the query text
        label = ControlledModelLabel(entity['label']).value
        by_label.setdefault(label, {})[entity['id']] = entity
    by_label['Team'] = {team['id']: team for team in contents['teams'].values()}

    async with driver.session() as session:
        for label, entities in by_label.items():
            result = await session.run(
                f"MATCH (n:{label}) WHERE n.id IN $ids "
                "RETURN n.id AS id, CASE WHEN n:Reference THEN n.description ELSE n.name END AS name",
                ids=list(entities)
            )
            found = {record['id']: record['name'] async for record in result}
            missing = set(entities) - set(found)
            if missing:
                raise RuntimeError(f"{label} ids {sorted(missing)} of the scenario are not in the database")
            for entity_id, entity in entities.items():
                entity['name'] = found[entity_id]


def files_dir_for(manifest_path: Path) -> Path:
    """Where a build's stored files are copied: beside the manifest, as <name>_files"""
    return manifest_path.parent / f"{manifest_path.stem.removesuffix('.manifest')}_files"


def copy_files(file_ids: Iterable[str], files_dir: Path) -> None:
    """Copy the files the scenarios stored in FILE_STORAGE_PATH, so they can be restored with the dump"""
    files_dir.mkdir(parents=True, exist_ok=True)
    for file_id in file_ids:
        shutil.copy2(Path(FILE_STORAGE_PATH, file_id), files_dir / file_id)


def write_manifest(manifest_path: Path, contents: dict, private: bool = False) -> None:
    """Write the manifest as JSON; a private one, holding credentials that aren't public, readable by the owner only"""
    text = json.dumps(contents, indent=2) + '\n'
    if not private:
        manifest_path.write_text(text)
        return
    with os.fdopen(os.open(manifest_path, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600), 'w') as file:
        file.write(text)
    manifest_path.chmod(0o600)
