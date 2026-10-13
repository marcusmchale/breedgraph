"""
The BreedCAFS fluorescence curves (README.md §7.1, 1_6_Extract_Records.md).

As in the datasets phase, a dataset holds the curves of one submission in one study,
and joins the Replicate scope of the other datasets of its submission (dataset_ids.csv).
Curves loaded without a submission (by a manual script, README §7.6) are left out where they repeat a submitted curve
of the same item with the same values, whatever the date; any others are kept, in a dataset of their own.
In the extracted data, all 16 repeat one.

Each dataset has its own data file, so that access to the files can follow access to the datasets:
a row per curve, with the BreedCAFS item uid, the unit id, the time and the replicate code that identify it,
then the curve's values, one column for each of the times (in seconds) all curves share.
The file is written to the data directory, stored as an upload is (FILE_STORAGE_PATH, by a new uuid),
referenced as a CSV data file whose schema describes these columns, and queued for archival.
Each curve is a record of the Fluorescence ~ Time variable, referencing its dataset's data file;
its row in the file is the one with its unit, time and replicate.

Each dataset, with its data file reference, is one transaction, recorded in curve_ids.csv as it completes,
so running this again creates only what was not created before.
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

from breedgraph.adapters.neo4j import Neo4jUnitOfWorkFactory
from breedgraph.adapters.neo4j.services.file_archival_service import Neo4jFileArchivalService
from breedgraph.domain.model.archive import FileArchivalRecord, ArchiveState, LocalState
from breedgraph.domain.model.datasets import DatasetInput, DataRecordInput, RecordGroup
from breedgraph.domain.model.references import DataFileInput, DataFormat
from breedgraph.service_layer.handlers.events.datasets import get_scale_and_categories

from breedcafs_migration.bootstrap import MigrationContext
from breedcafs_migration.datasets import DatasetIds, DatasetKey, entered_time, epoch_ms
from breedcafs_migration.ontology import OntologyIds
from breedcafs_migration.programs import ProgramIds, study_for, input_terms, field_countries
from breedcafs_migration.setup.config import BREEDCAFS_DATA_DIR

import logging
logger = logging.getLogger(__name__)

CURVE_INPUT = "Fluorescence ~ Time"
APPARATUS = "PocketPEA"
INDEX_COLUMNS = ["item_uid", "unit_id", "time", "replicate"]


@dataclass
class CurveIds:
    # Dataset key -> (data file reference id, dataset id)
    datasets: dict[DatasetKey, tuple[int, int]] = field(default_factory=dict)
    created: int = 0


def read_curves() -> list[dict]:
    with open(BREEDCAFS_DATA_DIR / 'curves.csv', encoding='utf-8-sig') as f:
        return list(csv.DictReader(f))


def time_of(curve: dict) -> str:
    """As entered: the date and time of day, or the date alone"""
    return str(entered_time(curve['time'], curve['text_time']))


def file_name(key: DatasetKey) -> str:
    """e.g. fluorescence_curves_nicaragua_2020-07-01T12-00-55.csv, or ..._without_submission.csv"""
    study, _, submission_time, _ = key
    submitted = str(epoch_ms(submission_time)).split('.')[0].replace(':', '-') if submission_time else 'without_submission'
    return f"fluorescence_curves_{study.lower().replace(' ', '_')}_{submitted}.csv"


def write_data_file(name: str, curves: list[dict], units: dict[str, int]) -> tuple[Path, list[float]]:
    x_values = json.loads(curves[0]['x_values'])
    if any(json.loads(curve['x_values']) != x_values for curve in curves):
        raise ValueError("The curves do not all share the same x values")
    path = BREEDCAFS_DATA_DIR / name
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


def planned_curves(ontology: OntologyIds) -> tuple[dict[DatasetKey, list[dict]], int]:
    """The curves of each dataset, and the number of curves left out as repeats of submitted curves"""
    curves = read_curves()
    submitted = {(c['item_uid'], c['y_values']) for c in curves if c['submission_time']}
    kept = [c for c in curves if c['submission_time'] or (c['item_uid'], c['y_values']) not in submitted]
    _, concept = ontology.inputs[(CURVE_INPUT, APPARATUS)]
    terms, countries = input_terms(), field_countries()
    by_dataset: dict[DatasetKey, list[dict]] = {}
    for curve in kept:
        study = study_for(terms.get(CURVE_INPUT, set()), countries[curve['item_uid'].split('_')[0]])
        by_dataset.setdefault((study, concept, curve['submission_time'], curve['submitter_id']), []).append(curve)
    return by_dataset, len(curves) - len(kept)


def read_mapping() -> CurveIds:
    path = BREEDCAFS_DATA_DIR / 'curve_ids.csv'
    ids = CurveIds()
    if path.exists():
        with open(path) as f:
            for row in csv.DictReader(f):
                key = (row['study'], int(row['concept_id']), row['submission_time'], row['submitter_id'])
                ids.datasets[key] = (int(row['reference_id']), int(row['dataset_id']))
    return ids


def write_mapping(ids: CurveIds) -> None:
    with open(BREEDCAFS_DATA_DIR / 'curve_ids.csv', 'w', newline='') as f:
        writer = csv.writer(f)
        writer.writerow(['study', 'concept_id', 'submission_time', 'submitter_id', 'reference_id', 'dataset_id'])
        for (study, concept, submission_time, submitter_id), (reference_id, dataset_id) in ids.datasets.items():
            writer.writerow([study, concept, submission_time, submitter_id, reference_id, dataset_id])


async def prepare_breedcafs_curves(
        uow_factory: Neo4jUnitOfWorkFactory,
        context: MigrationContext,
        ontology: OntologyIds,
        programs: ProgramIds,
        units: dict[str, int],
        datasets: DatasetIds
) -> CurveIds:
    by_dataset, left_out = planned_curves(ontology)
    if left_out:
        logger.info(f"Left out {left_out} curves loaded without a submission, repeating submitted curves")
    ids = read_mapping()
    archival = Neo4jFileArchivalService(driver=uow_factory.driver, queue=asyncio.Queue())

    for key, key_curves in by_dataset.items():
        if key in ids.datasets:
            continue
        study, concept, submission_time, submitter_id = key
        name = file_name(key)
        path, x_values = write_data_file(name, key_curves, units)
        file_id, file_size, file_hash = store_file(path, archival.file_storage_path)
        async with uow_factory.get_uow(user_id=context.user_id, write_team=context.team_id) as uow:
            reference = await uow.repositories.references.create(DataFileInput(
                description="Chlorophyll fluorescence induction curves migrated from BreedCAFS",
                filename=name,
                file_id=file_id,
                content_type="text/csv",
                format=DataFormat.CSV,
                schema=schema(x_values, len(key_curves))
            ))
            scale, categories = await get_scale_and_categories(concept_id=concept, ontology_service=uow.ontology)
            replicate = programs.replicate_groupings[study]
            dataset = await uow.repositories.datasets.create(DatasetInput(
                concept=concept, study=programs.studies[study], reference_ids=[reference.id]
            ))
            records = [
                DataRecordInput(
                    unit_id=units[curve['item_uid']],
                    start=entered_time(curve['time'], curve['text_time']),
                    end=entered_time(curve['time'], curve['text_time']),
                    groups=[RecordGroup(id=replicate, code=curve['replicate'])] if curve['replicate'] else None,
                    reference_ids=[reference.id]
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
        await archival.create(FileArchivalRecord(
            file_id=file_id,
            file_size=file_size,
            file_hash=file_hash,
            last_accessed=datetime.now(),
            archive_state=ArchiveState.ARCHIVAL_PENDING,
            local_state=LocalState.LOCAL
        ))
        ids.datasets[key] = (reference.id, dataset.id)
        ids.created += 1
        write_mapping(ids)

    logger.info(f"Prepared curves: {ids.created} datasets created, {len(ids.datasets)} in all, with {sum(len(c) for c in by_dataset.values())} curves")
    return ids
