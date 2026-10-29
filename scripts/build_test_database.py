#!/usr/bin/env python3
"""
Build the public, synthetic test database on an empty Neo4j and Redis: the read-policy scenario of the breedgraph
tests (tests/breedgraph/scenarios/read_policy_scenario.py), so the tests and this database describe the same world.
Every name and value is generated; nothing comes from real data. breedview's e2e tests run against a dump of it.
It also holds a study with record group codes of every extent and scope
(tests/breedgraph/scenarios/replicate_scenario.py), given in the manifest's "replicates" entry, units that came to
locations at dated positions (tests/breedgraph/scenarios/arrival_scenario.py), in its "arrivals" entry, and units at
positions in layouts for analysis position grouping (tests/breedgraph/scenarios/position_scenario.py), in its
"positions" entry, studies with licences given as files (tests/breedgraph/scenarios/licence_scenario.py), in its
"licences" entry, and records of a variable on a complex scale, which cite data files rather than hold values
(tests/breedgraph/scenarios/spectra_scenario.py), in its "spectra" entry.

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
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(ROOT / 'src'))
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(Path(__file__).parent))

import bcrypt
from faker import Faker

from breedgraph.config import FILE_STORAGE_PATH
from breedgraph.domain.model.accounts import UserInput, OntologyRole
from breedgraph.domain.model.controls import ControlledModelLabel
from breedgraph.domain.model.ontology import RecordGroupExtent

from database_builds import (
    git_commit, require_environment, empty_database, add_names, files_dir_for, copy_files, write_manifest
)

from tests.breedgraph.scenarios.replicate_scenario import (
    ReplicateScenarioBuilder, ReplicateScenario, DATASETS as REPLICATE_DATASETS, GROUPINGS, PROGRAM, TRIAL, STUDY,
    CONCEPTS, EXPECTED_CASES, EXPECTED_WINDOWED_READINGS, EXPECTED_PLOT_MEANS, BLOCK, BATCH, level_keys
)
from tests.breedgraph.scenarios.arrival_scenario import (
    ArrivalScenarioBuilder, ArrivalScenario, EXPECTED_ARRIVALS, EXPECTED_LIGHT, STORE, LAB_STORE,
    PROGRAM as ARRIVAL_PROGRAM, TRIAL as ARRIVAL_TRIAL, STUDY as ARRIVAL_STUDY, expected_germplasm
)
from tests.breedgraph.scenarios.position_scenario import (
    PositionScenarioBuilder, PositionScenario, CASES as POSITION_CASES, PROGRAM as POSITION_PROGRAM,
    TRIAL as POSITION_TRIAL, STUDY as POSITION_STUDY, level_key, grouping_input, term_inputs
)
from tests.breedgraph.scenarios.licence_scenario import (
    LicenceScenarioBuilder, LicenceScenario, STUDIES as LICENSED_STUDIES, PROGRAM as LICENCE_PROGRAM,
    TRIAL as LICENCE_TRIAL, DATA_FILE, PRIVATELY_CITED_FILE
)
from tests.breedgraph.scenarios.spectra_scenario import (
    SpectraScenarioBuilder, SpectraScenario, FILES as SPECTRA_FILES, RECORDS as SPECTRA_RECORDS,
    PROGRAM as SPECTRA_PROGRAM, TRIAL as SPECTRA_TRIAL, STUDY as SPECTRA_STUDY, SUBMISSION_STUDY, READ_ON
)
from tests.breedgraph.scenarios.ontology_builder import CANOPY_SPECTRUM
from tests.breedgraph.scenarios.scale_scenario import ScaleScenarioBuilder, ScaleScenario, ScaleParameters, study_key, field_key
from tests.breedgraph.scenarios.read_policy_scenario import (
    ReadPolicyScenarioBuilder, ReadPolicyScenario, VIEWERS, AFFILIATIONS, ENTITY_LABELS, DATASETS, REFERENCES,
    ATTRIBUTIONS, TEAM_CREDITED_BY
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
            # same_time height, observed at the plot subject (grouping.unit), term MEAN: without and with a MEAN
            # replicate aggregation
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


def arrivals_manifest(arrivals: ArrivalScenario, scenario: ReadPolicyScenario) -> dict:
    """
    Units that came to locations at dated positions, and the germplasm and factor records that come down to them
    (tests/breedgraph/scenarios/arrival_scenario.py). Arrivals list their units by name, newest first and undated (a
    null start) last, as each viewer sees them; germplasm is given by the read-policy germplasm's names (entities).
    """
    return {
        'program': {'id': arrivals.ids['program'], 'name': ARRIVAL_PROGRAM},
        'trial': {'id': arrivals.ids['trial'], 'name': ARRIVAL_TRIAL},
        'study': {'id': arrivals.ids['study'], 'name': ARRIVAL_STUDY},
        'locations': {
            location: {'id': arrivals.ids[STORE], 'name': LAB_STORE} if location == STORE else {'id': scenario[location]}
            for location in EXPECTED_ARRIVALS
        },
        'units': dict(sorted(arrivals.units.items())),
        'datasets': arrivals.datasets,
        'expected': {
            'arrivals': {
                location: {
                    viewer: [{'start': start, 'units': units} for start, units in arrivals_seen]
                    for viewer, arrivals_seen in by_viewer.items()
                }
                for location, by_viewer in EXPECTED_ARRIVALS.items()
            },
            'germplasm': {
                viewer: expected_germplasm(arrivals, viewer) for viewer in ('admin', 'writer', 'stranger', 'outsider')
            },
            'light': EXPECTED_LIGHT,
        },
    }


def positions_manifest(positions: PositionScenario, scenario: ReadPolicyScenario) -> dict:
    """
    Units at positions in layouts, and what analyses of them report (tests/breedgraph/scenarios/position_scenario.py):
    for each case, its datasets, its position grouping and terms as GraphQL input, the levels each viewer finds, with
    the count and mean of their observations, and the values of the records that can't be placed
    """
    def level(position_level, count, mean) -> dict:
        parts = {'key': level_key(positions, scenario, position_level), 'count': count, 'mean': mean}
        if position_level.location is not None:
            # a location of the read-policy scenario is named by its entity key
            parts['location'] = position_level.location
        else:
            parts['layout'], parts['axis'], parts['value'] = position_level.layout, position_level.axis, position_level.value
        return parts

    return {
        'program': {'id': positions.ids['program'], 'name': POSITION_PROGRAM},
        'trial': {'id': positions.ids['trial'], 'name': POSITION_TRIAL},
        'study': {'id': positions.ids['study'], 'name': POSITION_STUDY},
        'locations': dict(sorted(positions.locations.items())),
        'layouts': dict(sorted(positions.layouts.items())),
        'units': dict(sorted(positions.units.items())),
        'datasets': positions.datasets,
        'expected': {
            case.key: {
                'datasets': case.datasets,
                'grouping': grouping_input(case, scenario),
                'terms': term_inputs(case),
                'levels': {
                    viewer: [level(position_level, count, mean) for position_level, (count, mean) in levels.items()]
                    for viewer, levels in case.expected.items()
                },
                'unassigned': case.unassigned,
            }
            for case in POSITION_CASES
        },
    }


def licences_manifest(licences: LicenceScenario, files_dir: Path) -> dict:
    """
    Studies with licences given as files (tests/breedgraph/scenarios/licence_scenario.py): each study with its release,
    licence and height dataset, the data file a record of the public one cites, and the registered data file cited
    only by a private dataset of the registered one. The files are copied beside the manifest with the read-policy
    scenario's.
    """
    ids = licences.ids
    return {
        'program': {'id': ids['program'], 'name': LICENCE_PROGRAM},
        'trial': {'id': ids['trial'], 'name': LICENCE_TRIAL},
        'studies': {
            key: {
                'id': ids[f'{key}_study'],
                'name': study_name,
                'release': release.name,
                'licence': {
                    'id': ids[f'{key}_licence'], 'name': licence_name, 'filename': filename,
                    'file_id': licences.files[licence_name][0], 'path': str(files_dir / licences.files[licence_name][0])
                },
                'dataset': ids[f'{key}_dataset'],
            }
            for key, (study_name, release, licence_name, filename, _) in LICENSED_STUDIES.items()
        },
        'data_file': {'id': ids['data_file'], 'name': DATA_FILE, 'file_id': licences.files[DATA_FILE][0]},
        'privately_cited_file': {
            'id': ids['privately_cited_file'], 'name': PRIVATELY_CITED_FILE,
            'file_id': licences.files[PRIVATELY_CITED_FILE][0], 'study': 'registered'
        },
    }


def spectra_manifest(spectra: SpectraScenario, scenario: ReadPolicyScenario, files_dir: Path) -> dict:
    """
    Records of a variable on a complex scale, citing data files (tests/breedgraph/scenarios/spectra_scenario.py): the
    program, trial and studies, the variable, the dataset with each record by its read-policy unit and the files it
    cites, and the files. The files are copied beside the manifest with the read-policy scenario's.
    """
    ids = spectra.ids
    return {
        'program': {'id': ids['program'], 'name': SPECTRA_PROGRAM},
        'trial': {'id': ids['trial'], 'name': SPECTRA_TRIAL},
        'study': {'id': ids['study'], 'name': SPECTRA_STUDY},
        'submission_study': {'id': ids['submission_study'], 'name': SUBMISSION_STUDY},
        'concept': {'id': scenario['ontology_variable_spectrum'], 'name': CANOPY_SPECTRUM},
        'dataset': {
            'id': ids['dataset'],
            'records': {
                unit: {'id': spectra.records[unit], 'start': READ_ON, 'files': names}
                for unit, names in SPECTRA_RECORDS.items()
            },
        },
        'files': {
            name: {
                'reference_id': spectra.references[name],
                'file_id': spectra.files[name][0],
                'filename': filename,
                'path': str(files_dir / spectra.files[name][0]),
            }
            for name, (filename, _) in SPECTRA_FILES.items()
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
        arrivals: ArrivalScenario,
        positions: PositionScenario,
        licences: LicenceScenario,
        spectra: SpectraScenario,
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
        'teams': {
            # attribution: the team's own, or None where it takes its parent's
            team: {'id': scenario[team], 'attribution': ATTRIBUTIONS.get(team)}
            for team in ('root', 'child', 'other')
        },
        'ids': dict(sorted(scenario.ids.items())),
        'entities': {
            name: {
                'id': scenario[name],
                'label': label.value,
                'team': scenario.controls[name][0],
                'release': scenario.controls[name][1].name,
                'readable_by': [viewer for viewer in VIEWERS if scenario.readable(viewer, name)],
                # how it is credited (controlsAttributions), to those who can read it
                'credit': ATTRIBUTIONS[TEAM_CREDITED_BY[scenario.controls[name][0]]],
                # how each viewer sees a Person: FULL, ATTRIBUTION or RESTRICTED (docs/person.md §3)
                **(
                    {'person_views': {viewer: scenario.person_view(viewer, name) for viewer in VIEWERS}}
                    if label is ControlledModelLabel.PERSON else {}
                ),
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
        'arrivals': arrivals_manifest(arrivals, scenario),
        'positions': positions_manifest(positions, scenario),
        'licences': licences_manifest(licences, files_dir),
        'spectra': spectra_manifest(spectra, scenario, files_dir),
        **({'scale': scale_manifest(scale), 'perf': perf_manifest(scale)} if scale is not None else {}),
    }


async def build(seed: int, password: str, manifest_path: Path, scale_parameters: ScaleParameters | None):
    require_environment()
    Faker.seed(seed)

    files_dir = files_dir_for(manifest_path)
    async with empty_database() as services:
        uow_factory = services.uow_factory
        logger.info("Building the read-policy scenario")
        scenario = await ReadPolicyScenarioBuilder(
            uow_factory=uow_factory,
            state_store=services.state_store,
            archival_service=services.archival_service(),
            file_storage_path=FILE_STORAGE_PATH,
            users=users(password)
        ).build()
        logger.info("Building the replicates study")
        replicates = await ReplicateScenarioBuilder(uow_factory, scenario).build()
        logger.info("Building the arrivals")
        arrivals = await ArrivalScenarioBuilder(uow_factory, scenario).build()
        logger.info("Building the positions")
        positions = await PositionScenarioBuilder(uow_factory, scenario).build()
        logger.info("Building the licences")
        licences = await LicenceScenarioBuilder(
            uow_factory, scenario, archival_service=services.archival_service(), file_storage_path=FILE_STORAGE_PATH
        ).build()
        logger.info("Building the spectra")
        spectra = await SpectraScenarioBuilder(
            uow_factory, scenario, archival_service=services.archival_service(), file_storage_path=FILE_STORAGE_PATH
        ).build()
        scale = None
        if scale_parameters is not None:
            logger.info(f"Adding data at scale: {vars(scale_parameters)}")
            scale = await ScaleScenarioBuilder(uow_factory, scenario, scale_parameters).build()
        # the scenario creates countries without the message bus
        await services.read_models.refresh()

        contents = manifest(scenario, replicates, arrivals, positions, licences, spectra, seed, password, files_dir, scale)
        await add_names(services.driver, contents)

    copy_files(
        [file_id for file_id, _ in [*scenario.files.values(), *licences.files.values(), *spectra.files.values()]],
        files_dir
    )
    write_manifest(manifest_path, contents)

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
