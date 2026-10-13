"""
The BreedCAFS fluorescence curves (README.md §7.1, 1_6_Extract_Records.md).

The curves of curves.csv are written to one data file, fluorescence_curves.csv:
a row per curve, with the BreedCAFS item uid, the unit id, the time and the replicate code that identify it,
then the curve's values, one column for each of the times (in seconds) all curves share.
The file is stored as an upload is (FILE_STORAGE_PATH, by a new uuid), referenced as a CSV data file
whose schema describes these columns, and queued for archival.

Each curve is a record of the Fluorescence ~ Time variable, referencing the data file; its row in the file
is the one with its unit, time and replicate. As in the datasets phase, a dataset holds the curves of one submission
in one study, and joins the Replicate scope of the other datasets of its submission (dataset_ids.csv).
The 16 curves loaded without a submission each repeat a submitted curve of the same item and day;
they are kept, in a dataset of their own.

Writes curve_ids.csv, with the data file reference and the curve datasets; running this again does nothing
once they are all created.
"""
import asyncio
import csv
import hashlib
import json
import shutil
import uuid
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path

from numpy import datetime64

from breedgraph.adapters.neo4j import Neo4jUnitOfWorkFactory
from breedgraph.adapters.neo4j.services.file_archival_service import Neo4jFileArchivalService
from breedgraph.domain.model.archive import FileArchivalRecord, ArchiveState, LocalState
from breedgraph.domain.model.datasets import DatasetInput, DataRecordInput, RecordGroup
from breedgraph.domain.model.references import DataFileInput, DataFormat
from breedgraph.service_layer.handlers.events.datasets import get_scale_and_categories

from breedcafs_migration.bootstrap import MigrationContext
from breedcafs_migration.datasets import DatasetIds, DatasetKey, entered_time
from breedcafs_migration.ontology import OntologyIds
from breedcafs_migration.programs import ProgramIds, study_for, input_terms, field_countries
from breedcafs_migration.setup.config import BREEDCAFS_DATA_DIR

import logging
logger = logging.getLogger(__name__)

CURVE_INPUT = "Fluorescence ~ Time"
APPARATUS = "PocketPEA"
DATA_FILE = 'fluorescence_curves.csv'
INDEX_COLUMNS = ["item_uid", "unit_id", "time", "replicate"]


@dataclass
class CurveIds:
    reference_id: int | None = None
    datasets: dict[DatasetKey, int] = field(default_factory=dict)
    created: int = 0


def read_curves() -> list[dict]:
    with open(BREEDCAFS_DATA_DIR / 'curves.csv', encoding='utf-8-sig') as f:
        return list(csv.DictReader(f))


def time_of(curve: dict) -> str:
    """As entered: the date and time of day, or the date alone"""
    return str(entered_time(curve['time'], curve['text_time']))


def write_data_file(curves: list[dict], units: dict[str, int]) -> tuple[Path, list[float]]:
    x_values = json.loads(curves[0]['x_values'])
    if any(json.loads(curve['x_values']) != x_values for curve in curves):
        raise ValueError("The curves do not all share the same x values")
    path = BREEDCAFS_DATA_DIR / DATA_FILE
    with open(path, 'w', newline='') as f:
        writer = csv.writer(f)
        writer.writerow([*INDEX_COLUMNS, *x_values])
        for curve in curves:
            writer.writerow([
                curve['item_uid'], units[curve['item_uid']], time_of(curve), curve['replicate'],
                *json.loads(curve['y_values'])
            ])
    return path, x_values


def schema(x_values: list[float], rows: int) -> dict:
    return {
        "description": (
            "Chlorophyll fluorescence induction curves (PocketPEA), one row per record. "
            "A record's row is the one with its unit, time and replicate; "
            "the other columns are the fluorescence at the times, in seconds, given as their names."
        ),
        "index_columns": INDEX_COLUMNS,
        "time_columns": len(x_values),
        "shape": [rows, len(INDEX_COLUMNS) + len(x_values)],
        "dtype": "float64",
    }


def store_file(path: Path, storage: Path) -> tuple[str, int, str]:
    """Copy the file into the file store, as an upload is saved. Returns its uuid, size and hash."""
    file_id = str(uuid.uuid4())
    storage.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(path, storage / file_id)
    return file_id, path.stat().st_size, hashlib.sha256(path.read_bytes()).hexdigest()


def read_mapping() -> CurveIds:
    path = BREEDCAFS_DATA_DIR / 'curve_ids.csv'
    ids = CurveIds()
    if path.exists():
        with open(path) as f:
            for row in csv.DictReader(f):
                ids.reference_id = int(row['reference_id'])
                if row['dataset_id']:
                    key = (row['study'], int(row['concept_id']), row['submission_time'], row['submitter_id'])
                    ids.datasets[key] = int(row['dataset_id'])
    return ids


def write_mapping(ids: CurveIds) -> None:
    with open(BREEDCAFS_DATA_DIR / 'curve_ids.csv', 'w', newline='') as f:
        writer = csv.writer(f)
        writer.writerow(['reference_id', 'study', 'concept_id', 'submission_time', 'submitter_id', 'dataset_id'])
        writer.writerow([ids.reference_id, '', '', '', '', ''])
        for (study, concept, submission_time, submitter_id), dataset_id in ids.datasets.items():
            writer.writerow([ids.reference_id, study, concept, submission_time, submitter_id, dataset_id])


async def create_data_file(
        uow_factory: Neo4jUnitOfWorkFactory, context: MigrationContext, curves: list[dict], units: dict[str, int]
) -> int:
    path, x_values = write_data_file(curves, units)
    archival = Neo4jFileArchivalService(driver=uow_factory.driver, queue=asyncio.Queue())
    file_id, file_size, file_hash = store_file(path, archival.file_storage_path)
    async with uow_factory.get_uow(user_id=context.user_id, write_team=context.team_id) as uow:
        reference = await uow.repositories.references.create(DataFileInput(
            description="Chlorophyll fluorescence induction curves migrated from BreedCAFS",
            filename=DATA_FILE,
            file_id=file_id,
            content_type="text/csv",
            format=DataFormat.CSV,
            schema=schema(x_values, len(curves))
        ))
        await uow.commit()
    await archival.create(FileArchivalRecord(
        file_id=file_id,
        file_size=file_size,
        file_hash=file_hash,
        last_accessed=datetime.now(),
        archive_state=ArchiveState.ARCHIVAL_PENDING,
        local_state=LocalState.LOCAL
    ))
    return reference.id


async def prepare_breedcafs_curves(
        uow_factory: Neo4jUnitOfWorkFactory,
        context: MigrationContext,
        ontology: OntologyIds,
        programs: ProgramIds,
        units: dict[str, int],
        datasets: DatasetIds
) -> CurveIds:
    curves = read_curves()
    ids = read_mapping()
    if ids.reference_id is None:
        ids.reference_id = await create_data_file(uow_factory, context, curves, units)
        ids.created += 1
        write_mapping(ids)

    _, concept = ontology.inputs[(CURVE_INPUT, APPARATUS)]
    terms, countries = input_terms(), field_countries()
    by_dataset: dict[DatasetKey, list[dict]] = {}
    for curve in curves:
        study = study_for(terms.get(CURVE_INPUT, set()), countries[curve['item_uid'].split('_')[0]])
        by_dataset.setdefault((study, concept, curve['submission_time'], curve['submitter_id']), []).append(curve)

    for key, key_curves in by_dataset.items():
        if key in ids.datasets:
            continue
        study, _, submission_time, submitter_id = key
        async with uow_factory.get_uow(user_id=context.user_id, write_team=context.team_id) as uow:
            scale, categories = await get_scale_and_categories(concept_id=concept, ontology_service=uow.ontology)
            replicate = programs.replicate_groupings[study]
            dataset = await uow.repositories.datasets.create(DatasetInput(concept=concept, study=programs.studies[study]))
            records = [
                DataRecordInput(
                    unit_id=units[curve['item_uid']],
                    start=entered_time(curve['time'], curve['text_time']),
                    end=entered_time(curve['time'], curve['text_time']),
                    groups=[RecordGroup(id=replicate, code=curve['replicate'])] if curve['replicate'] else None,
                    reference_ids=[ids.reference_id]
                )
                for curve in key_curves
            ]
            errors = [error for error in dataset.add_records(records, scale, categories, [replicate]) if error]
            if errors:
                raise ValueError(f"{len(errors)} curves of {key} do not parse, e.g. {errors[:3]}")
            # Join the Replicate scope of the other datasets of the same submission in the study
            submission = {
                dataset_id for (other_study, _, other_time, other_submitter), dataset_id in datasets.datasets.items()
                if (other_study, other_time, other_submitter) == (study, submission_time, submitter_id)
            }
            program = await uow.repositories.programs.get(study_id=programs.studies[study])
            program.get_study(programs.studies[study]).get_grouping(grouping_id=replicate).merge_dataset_scope(
                submission | {dataset.id}
            )
            await uow.commit()
        ids.datasets[key] = dataset.id
        ids.created += 1
        write_mapping(ids)

    logger.info(f"Prepared curves: {ids.created} created, {len(ids.datasets)} curve datasets with {len(curves)} curves")
    return ids
