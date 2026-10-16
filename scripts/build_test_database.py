#!/usr/bin/env python3
"""
Build the public, synthetic test database on an empty Neo4j and Redis: the read-policy scenario of the breedgraph
tests (tests/breedgraph/scenarios/read_policy_scenario.py), so the tests and this database describe the same world.
Every name and value is generated; nothing comes from real data. breedview's e2e tests run against a dump of it.
It also holds a study with record group codes of every extent and scope
(tests/breedgraph/scenarios/replicate_scenario.py), given in the manifest's "replicates" entry.

Writes a manifest (JSON) with the accounts' credentials, the ids of every entity by its scenario name, the controls
each entity was written under, what each viewer can read, and the files. The files themselves are written to
FILE_STORAGE_PATH, as uploads would be, and copied beside the manifest so they can be restored with the dump.

Needs the instance environment loaded, and the test extras installed (faker, for the generated names):

    set -a; . instance/breedgraph.env; . instance/private.breedgraph.env; set +a
    python scripts/build_test_database.py --manifest instance/neo4j_archive/test_databases/test_database.manifest.json

With --scale, data at scale for breedview's performance scripts is added (tests/breedgraph/scenarios/scale_scenario.py):
about 100,000 units and 44,000 records with the defaults, which takes a while; the manifest's "perf" entry gives the
scripts' study, concept and field. The sizes can be set (--fields, --trees-per-field and so on) for a smaller build.

Neo4j and Redis must be empty (a run of the breedgraph test suite leaves them so). Then dump the database with
scripts/backup.sh and move the dump beside the manifest as test_database.dump.
"""
import argparse
import asyncio
import json
import shutil
import subprocess
import sys
from asyncio import Queue
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(ROOT / 'src'))
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(Path(__file__).parent))

import bcrypt
import redis.asyncio as redis
from faker import Faker

from breedgraph.config import FILE_STORAGE_PATH, COUNTRY_CODES_PATH, get_redis_host_and_port
from breedgraph.domain.model.accounts import UserInput, OntologyRole
from breedgraph.domain.model.controls import ControlledModelLabel
from breedgraph.domain.model.ontology import RecordGroupExtent
from breedgraph.adapters.neo4j.driver import Neo4jAsyncDriver
from breedgraph.adapters.neo4j.unit_of_work import Neo4jUnitOfWorkFactory
from breedgraph.adapters.neo4j.services.file_archival_service import Neo4jFileArchivalService
from breedgraph.adapters.redis.read_models import RedisReadModels
from breedgraph.adapters.redis.state_store import RedisStateStore

from setup_initial_data import ensure_empty_db, create_schema, create_system_account, create_initial_ontology_entries
from load_state_store import is_redis_empty

from tests.breedgraph.scenarios.replicate_scenario import (
    ReplicateScenarioBuilder, ReplicateScenario, DATASETS as REPLICATE_DATASETS, GROUPINGS, PROGRAM, TRIAL, STUDY,
    CONCEPTS, EXPECTED_CASES, EXPECTED_WINDOWED_READINGS, EXPECTED_PLOT_MEANS, BLOCK, BATCH, level_keys
)
from tests.breedgraph.scenarios.scale_scenario import ScaleScenarioBuilder, ScaleScenario, ScaleParameters, study_key, field_key
from tests.breedgraph.scenarios.read_policy_scenario import (
    ReadPolicyScenarioBuilder, ReadPolicyScenario, VIEWERS, AFFILIATIONS, ENTITY_LABELS, DATASETS, REFERENCES
)

import logging
logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
logging.getLogger('faker').setLevel(logging.WARNING)
logger = logging.getLogger(__name__)

# The accounts, with names and addresses that can never be real (example.org is reserved, RFC 2606)
ACCOUNTS = {
    'admin': ('Readpolicy Admin', OntologyRole.ADMIN),
    'writer': ('Readpolicy Writer', OntologyRole.CONTRIBUTOR),
    'stranger': ('Readpolicy Stranger', OntologyRole.CONTRIBUTOR),
    'outsider': ('Readpolicy Outsider', OntologyRole.CONTRIBUTOR),
}


def users(password: str) -> dict[str, UserInput]:
    password_hash = bcrypt.hashpw(password.encode(), bcrypt.gensalt()).decode()
    return {
        viewer: UserInput(
            name=f"readpolicy_{viewer}",
            fullname=fullname,
            email=f"readpolicy_{viewer}@example.org",
            password_hash=password_hash,
            email_verified=True,
            ontology_role=role
        )
        for viewer, (fullname, role) in ACCOUNTS.items()
    }


def git_commit() -> str | None:
    try:
        return subprocess.run(
            ['git', 'rev-parse', 'HEAD'], cwd=ROOT, capture_output=True, text=True, check=True
        ).stdout.strip()
    except (OSError, subprocess.CalledProcessError):
        return None


def scale_manifest(scale: ScaleScenario) -> dict:
    return {
        'parameters': vars(scale.parameters),
        'unit_count': scale.unit_count,
        'record_count': scale.record_count,
        'names': scale.names,
        'ids': scale.ids,
        'dataset_ids': scale.dataset_ids,
    }


def replicates_manifest(replicates: ReplicateScenario, scenario: ReadPolicyScenario) -> dict:
    """The replicates study, and what analyses of it report (tests/breedgraph/scenarios/replicate_scenario.py)"""
    concept_names = {key: name for key, name in CONCEPTS.values()}
    within_unit = {name for name, (_, extent, _) in GROUPINGS.items() if extent == RecordGroupExtent.WITHIN_UNIT}

    def units_with_replicates(records) -> list[int]:
        replicated = [record.unit for record in records if any(name in within_unit for name, _ in record.groups)]
        return sorted({replicates.units[unit] for unit in replicated if replicated.count(unit) > 1})

    def levels(key, records) -> dict[str, list[str]]:
        groupings = dict.fromkeys(name for record in records for name, _ in record.groups)
        return {name: level_keys(replicates, key, name) for name in groupings}

    return {
        'program': {'id': replicates.ids['program'], 'name': PROGRAM},
        'trial': {'id': replicates.ids['trial'], 'name': TRIAL},
        'study': {'id': replicates.ids['study'], 'name': STUDY},
        'groupings': {
            name: {
                'id': replicates.groupings[name],
                'type': scenario[type_key],
                'extent': extent.name,
                'scope': scope.name,
            }
            for name, (type_key, extent, scope) in GROUPINGS.items()
        },
        'datasets': {
            key: {
                'id': replicates.datasets[key],
                'concept': scenario[concept_key],
                'concept_name': concept_names[concept_key],
                'record_count': len(records),
                'units_with_replicates': units_with_replicates(records),
            }
            for key, (concept_key, records) in REPLICATE_DATASETS.items()
        },
        'units': dict(sorted(replicates.units.items())),
        'concepts': {concept: {'id': scenario[key], 'name': name} for concept, (key, name) in CONCEPTS.items()},
        'expected': {
            # an analysis of the dataset's concept as its only term, with no dimensions
            'cases': [
                {
                    'dataset': case.dataset,
                    'aggregation': case.aggregation,
                    'replicate_aggregation': (
                        {'aggregation': case.replicate_aggregation[0], 'window': case.replicate_aggregation[1]}
                        if case.replicate_aggregation else None
                    ),
                    'error': (
                        {'code': case.error[0], 'path_end': case.error[1], 'record_count': case.error[2]}
                        if case.error else None
                    ),
                    'warnings': list(case.warnings),
                }
                for case in EXPECTED_CASES
            ],
            'windowed_readings_per_tree': {
                window or 'none': readings for window, readings in EXPECTED_WINDOWED_READINGS.items()
            },
            # same_time height, grouping.unit by plot, term MEAN: without and with a MEAN replicate aggregation
            'plot_means': {
                plot: {'unit_id': replicates.units[plot], 'pooled': pooled, 'mean_of_tree_means': two_stage}
                for plot, (pooled, two_stage) in EXPECTED_PLOT_MEANS.items()
            },
            # nested level keys of a record group dimension of each grouping, by dataset (docs/analysis.md §6)
            'levels': {key: levels(key, records) for key, (_, records) in REPLICATE_DATASETS.items()},
            'blocks': {
                'block_levels': len(level_keys(replicates, 'blocks', BLOCK)),
                'block_levels_with_block_1_shared': len(level_keys(replicates, 'blocks', BLOCK)) - 1,
                'batch_levels': len(level_keys(replicates, 'blocks', BATCH)),
            },
        },
    }


def perf_manifest(scale: ScaleScenario) -> dict:
    """The defaults of breedview's performance scripts (perf in its fixture): a large study, its variable, a large field"""
    return {
        'study': scale.names[study_key(1)],
        'concept': "Tree Height (mm)",
        'field': scale.names[field_key(1)],
    }


def manifest(
        scenario: ReadPolicyScenario,
        replicates: ReplicateScenario,
        seed: int,
        password: str,
        files_dir: Path,
        scale: ScaleScenario | None
) -> dict:
    return {
        'description': "The breedgraph read-policy scenario: synthetic data for tests (see scripts/build_test_database.py)",
        'built_at': datetime.now(timezone.utc).isoformat(),
        'breedgraph_commit': git_commit(),
        'seed': seed,
        'accounts': {
            viewer: {
                'user_id': scenario[viewer],
                'username': f"readpolicy_{viewer}",
                'email': f"readpolicy_{viewer}@example.org",
                'password': password,
                'affiliations': {
                    team: sorted(access.name for access in accesses)
                    for team, accesses in AFFILIATIONS[viewer].items()
                },
            }
            for viewer in ACCOUNTS
        },
        'teams': {team: {'id': scenario[team]} for team in ('root', 'child', 'other')},
        'ids': dict(sorted(scenario.ids.items())),
        'entities': {
            name: {
                'id': scenario[name],
                'label': label.value,
                'team': scenario.controls[name][0],
                'release': scenario.controls[name][1].name,
                'readable_by': [viewer for viewer in VIEWERS if scenario.readable(viewer, name)],
            }
            for name, label in sorted(ENTITY_LABELS.items())
        },
        'datasets': {
            name: {
                'record_count': len(dataset['records']),
                'unit_count': len({unit for unit, _, _ in dataset['records']}),
            }
            for name, dataset in DATASETS.items()
        },
        'files': {
            name: {
                'reference_id': scenario[name],
                'file_id': file_id,
                'filename': f"{name}.csv",
                'description': REFERENCES[name][1],
                'path': str(files_dir / file_id),
            }
            for name, (file_id, _) in scenario.files.items()
        },
        'replicates': replicates_manifest(replicates, scenario),
        **({'scale': scale_manifest(scale), 'perf': perf_manifest(scale)} if scale is not None else {}),
    }


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


async def build(seed: int, password: str, manifest_path: Path, scale_parameters: ScaleParameters | None):
    if not FILE_STORAGE_PATH:
        raise RuntimeError("FILE_STORAGE_PATH is not set: load the instance environment first")
    if not Path(COUNTRY_CODES_PATH).is_file():
        # the scenario's location trees are countries from this file, which the state store holds
        raise RuntimeError(f"No country codes at COUNTRY_CODES_PATH ({COUNTRY_CODES_PATH}), e.g. src/data/country_codes.csv")
    Faker.seed(seed)

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
        # no message bus: account events would send email, and the scenario writes what uploads would
        uow_factory = Neo4jUnitOfWorkFactory(driver)
        system_account = await create_system_account(uow_factory)
        await create_initial_ontology_entries(system_account, uow_factory)

        logger.info("Loading the state store")
        read_models = await RedisReadModels.create(driver=driver, connection=connection)
        await read_models.refresh()

        logger.info("Building the read-policy scenario")
        scenario = await ReadPolicyScenarioBuilder(
            uow_factory=uow_factory,
            state_store=RedisStateStore(connection),
            archival_service=Neo4jFileArchivalService(driver=driver, queue=Queue()),
            file_storage_path=FILE_STORAGE_PATH,
            users=users(password)
        ).build()
        logger.info("Building the replicates study")
        replicates = await ReplicateScenarioBuilder(uow_factory, scenario).build()
        scale = None
        if scale_parameters is not None:
            logger.info(f"Adding data at scale: {vars(scale_parameters)}")
            scale = await ScaleScenarioBuilder(uow_factory, scenario, scale_parameters).build()
        # the scenario creates countries without the message bus
        await read_models.refresh()

        files_dir = manifest_path.parent / f"{manifest_path.stem.removesuffix('.manifest')}_files"
        contents = manifest(scenario, replicates, seed, password, files_dir, scale)
        await add_names(driver, contents)
    finally:
        await connection.aclose()
        await driver.close()

    files_dir.mkdir(parents=True, exist_ok=True)
    for file_id, _ in scenario.files.values():
        shutil.copy2(Path(FILE_STORAGE_PATH, file_id), files_dir / file_id)
    manifest_path.write_text(json.dumps(contents, indent=2) + '\n')

    logger.info(f"Built {len(ENTITY_LABELS)} entities; manifest at {manifest_path}, files in {files_dir}")
    logger.info("Next: dump the database with scripts/backup.sh and rename the dump to sit beside the manifest")


def main():
    parser = argparse.ArgumentParser(description=__doc__.split('\n\n')[0], formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument('--manifest', type=Path, required=True, help="where to write the manifest (JSON)")
    parser.add_argument('--seed', type=int, default=1, help="seed for the generated names and text (default 1)")
    parser.add_argument(
        '--password', default='readpolicy-test-password',
        help="the password of every account; the database is public, so this is too (default readpolicy-test-password)"
    )
    parser.add_argument('--scale', action='store_true', help="add data at scale for the performance scripts")
    defaults = ScaleParameters()
    for name, value in vars(defaults).items():
        parser.add_argument(f"--{name.replace('_', '-')}", type=int, default=value, help=f"with --scale (default {value})")
    args = parser.parse_args()
    scale_parameters = ScaleParameters(**{name: getattr(args, name) for name in vars(defaults)}) if args.scale else None
    if args.manifest.exists():
        parser.error(f"{args.manifest} exists: remove it or choose another path")
    try:
        asyncio.run(build(args.seed, args.password, args.manifest, scale_parameters))
    except Exception as e:
        logger.error(f"Build failed: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
