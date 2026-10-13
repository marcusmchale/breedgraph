"""
Datasets of the BreedCAFS records (README.md §7.6, 1_6_Extract_Records.md).

Each record in records.csv is assigned:
  - its variable or factor, from its input, and for photosynthesis inputs its apparatus (ontology_ids.csv):
    the Photosynthetic Analysis Apparatus recorded for its item at the same time, or the only apparatus of its input,
    or else PocketPEA where JIP-test parameters, only measured by PocketPEA, were recorded with it;
  - its study, by study_for (README §7.5);
  - its unit (unit_ids.csv);
  - its value, as parsed against the scale of its variable or factor ("True" and "False" as Yes and No);
  - its time: observations start and end at their time, conditions at their start and end where given,
    to the minute where a time of day was entered (text_time), and otherwise as the date alone,
    as BreedCAFS set the time of day of dates to 12:00;
  - its replicate code, in the study's Replicate grouping.
A dataset holds the records of one variable or factor, from one submission, in one study.
Records loaded without a submission (by a manual script, README §7.6) are left out where they repeat a submitted record:
the same item, input, value and replicate code, whatever the date, as the submitted dates are trusted.
Any that do not repeat one are kept, one dataset per variable and study; in the extracted data, all repeat one.
The Replicate grouping of each study is scoped to the datasets of each submission,
so replicate codes are only compared within the records submitted together.
The factor records of factor_records.csv (block treatments and branch strata) are one dataset per factor and study.

Left out: the records of duplicate items (units.DUPLICATE_ITEMS), the apparatus records (used to choose the variable), "Set harvest time" records (all the default "12:00",
the harvest date being recorded), and curves (curves.py), whose complex scale needs a data file.

Each study and submission is one transaction, recorded in dataset_ids.csv as it completes,
so running this again creates only the datasets not created before.
"""
import csv
from dataclasses import dataclass, field

from numpy import datetime64

from breedgraph.adapters.neo4j import Neo4jUnitOfWorkFactory
from breedgraph.domain.model.datasets import DatasetInput, DataRecordInput, RecordGroup
from breedgraph.domain.model.ontology import OntologyEntryLabel
from breedgraph.service_layer.handlers.events.datasets import get_scale_and_categories

from breedcafs_migration.bootstrap import MigrationContext
from breedcafs_migration.ontology import OntologyIds
from breedcafs_migration.programs import ProgramIds, study_for, input_terms, field_countries
from breedcafs_migration.units import DUPLICATE_ITEMS
from breedcafs_migration.setup.config import BREEDCAFS_DATA_DIR

import logging
logger = logging.getLogger(__name__)

APPARATUS_INPUT = "Photosynthetic Analysis Apparatus"
LEFT_OUT_INPUTS = {APPARATUS_INPUT, "Set harvest time"}
# Parameters of the JIP-test, only measured with PocketPEA
POCKET_PEA = "PocketPEA"
BOOLEAN_VALUES = {"true": "Yes", "false": "No"}
DESIGN = "design"  # the submission key of factor records not from BreedCAFS inputs

# (study key, concept id, submission time, submitter id)
DatasetKey = tuple[str, int, str, str]


@dataclass
class RecordPlan:
    item_uid: str
    value: str
    start: datetime64 | None = None
    end: datetime64 | None = None
    replicate: str | None = None


@dataclass
class DatasetIds:
    datasets: dict[DatasetKey, int] = field(default_factory=dict)
    records: int = 0
    created: int = 0
    repeats_left_out: int = 0


def read_csv(name: str) -> list[dict[str, str]]:
    with open(BREEDCAFS_DATA_DIR / name, encoding='utf-8-sig') as f:
        return list(csv.DictReader(f))


def epoch_ms(value: str) -> datetime64 | None:
    """BreedCAFS times are milliseconds since the epoch, or False where not given"""
    return datetime64(int(value), 'ms') if value and value.lstrip('-').isdigit() else None


def entered_time(value: str, text: str) -> datetime64 | None:
    """
    A BreedCAFS time as it was entered: the date and time of day (text) to the minute,
    or the date alone where no time of day was entered and BreedCAFS set it to 12:00.
    """
    time = epoch_ms(value)
    if time is None:
        return None
    return time.astype('datetime64[m]') if text else time.astype('datetime64[D]')


class DatasetPlan:
    """The datasets to create and their records, from the extracted files"""

    def __init__(self, ontology: OntologyIds):
        self.ontology = ontology
        self.terms = input_terms()
        self.countries = field_countries()
        self.apparatus_options: dict[str, set[str]] = {}
        for input_name, apparatus in ontology.inputs:
            self.apparatus_options.setdefault(input_name, set()).add(apparatus)
        self.datasets: dict[DatasetKey, list[RecordPlan]] = {}
        self.label: dict[int, OntologyEntryLabel] = {}
        self.repeats_left_out = 0

    def study(self, input_name: str, item_uid: str) -> str:
        return study_for(self.terms.get(input_name, set()), self.countries[item_uid.split('_')[0]])

    def add(self, key: DatasetKey, record: RecordPlan) -> None:
        self.datasets.setdefault(key, []).append(record)

    def apparatus(self, row: dict, recorded: dict[tuple[str, str], str], jip_times: set[tuple[str, str]]) -> str:
        options = self.apparatus_options[row['input']]
        if options == {''}:
            return ''
        apparatus = recorded.get((row['item_uid'], row['time']))
        if apparatus in options:
            return apparatus
        if len(options) == 1:
            return next(iter(options))
        if POCKET_PEA in options and (row['item_uid'], row['time']) in jip_times:
            return POCKET_PEA
        raise ValueError(f"No apparatus for {row['input']} of {row['item_uid']} at {row['time']}")

    def read_records(self) -> None:
        rows = read_csv('records.csv')
        recorded = {(r['item_uid'], r['time']): r['value'] for r in rows if r['input'] == APPARATUS_INPUT}
        # JIP-test parameters: the inputs measured only with PocketPEA
        jip_inputs = {name for name, options in self.apparatus_options.items() if options == {POCKET_PEA}}
        jip_times = {(r['item_uid'], r['time']) for r in rows if r['input'] in jip_inputs}
        repeat_key = lambda r: (r['item_uid'], r['input'], r['value'], r['replicate'])
        submitted = {repeat_key(r) for r in rows if r['submission_time']}
        for row in rows:
            if row['input'] in LEFT_OUT_INPUTS or row['item_uid'] in DUPLICATE_ITEMS:
                continue
            if not row['submission_time'] and repeat_key(row) in submitted:
                self.repeats_left_out += 1
                continue
            label, concept = self.ontology.inputs[(row['input'], self.apparatus(row, recorded, jip_times))]
            self.label[concept] = label
            if row['record_type'] == 'Condition':
                start = entered_time(row['start'], row['text_start_time'])
                end = entered_time(row['end'], row['text_end_time'])
            else:
                start = end = entered_time(row['time'], row['text_time'])
            key = (self.study(row['input'], row['item_uid']), concept, row['submission_time'], row['submitter_id'])
            self.add(key, RecordPlan(
                item_uid=row['item_uid'], value=row['value'], start=start, end=end, replicate=row['replicate'] or None
            ))

    def read_factor_records(self) -> None:
        for row in read_csv('factor_records.csv'):
            concept = self.ontology.design_factors[row['factor']]
            self.label[concept] = OntologyEntryLabel.FACTOR
            key = (self.study('', row['item_uid']), concept, DESIGN, '')
            self.add(key, RecordPlan(item_uid=row['item_uid'], value=row['category']))

    def submissions(self) -> dict[tuple[str, str, str], list[DatasetKey]]:
        """Dataset keys by study and submission, the transactions to commit"""
        submissions = {}
        for key in self.datasets:
            study, _, submission_time, submitter_id = key
            submissions.setdefault((study, submission_time, submitter_id), []).append(key)
        return submissions


def value_for(value: str, scale, categories) -> str:
    if categories and value.casefold() in BOOLEAN_VALUES:
        names = {name.casefold() for category in categories for name in category.names}
        if BOOLEAN_VALUES[value.casefold()].casefold() in names:
            return BOOLEAN_VALUES[value.casefold()]
    return value


def read_mapping() -> dict[DatasetKey, int]:
    path = BREEDCAFS_DATA_DIR / 'dataset_ids.csv'
    if not path.exists():
        return {}
    with open(path) as f:
        return {
            (row['study'], int(row['concept_id']), row['submission_time'], row['submitter_id']): int(row['dataset_id'])
            for row in csv.DictReader(f)
        }


def write_mapping(ids: DatasetIds) -> None:
    with open(BREEDCAFS_DATA_DIR / 'dataset_ids.csv', 'w', newline='') as f:
        writer = csv.writer(f)
        writer.writerow(['study', 'concept_id', 'submission_time', 'submitter_id', 'dataset_id'])
        for (study, concept, submission_time, submitter_id), dataset_id in ids.datasets.items():
            writer.writerow([study, concept, submission_time, submitter_id, dataset_id])


async def prepare_breedcafs_datasets(
        uow_factory: Neo4jUnitOfWorkFactory,
        context: MigrationContext,
        ontology: OntologyIds,
        programs: ProgramIds,
        units: dict[str, int]
) -> DatasetIds:
    plan = DatasetPlan(ontology)
    plan.read_records()
    plan.read_factor_records()
    ids = DatasetIds(datasets=read_mapping(), repeats_left_out=plan.repeats_left_out)
    if plan.repeats_left_out:
        logger.info(f"Left out {plan.repeats_left_out} records loaded without a submission, repeating submitted records")
    scales = {}

    for (study, submission_time, submitter_id), keys in plan.submissions().items():
        if all(key in ids.datasets for key in keys):
            continue
        async with uow_factory.get_uow(user_id=context.user_id, write_team=context.team_id) as uow:
            program = await uow.repositories.programs.get(study_id=programs.studies[study])
            replicate = programs.replicate_groupings[study]
            created = {}
            for key in keys:
                concept = key[1]
                if concept not in scales:
                    scales[concept] = await get_scale_and_categories(concept_id=concept, ontology_service=uow.ontology)
                scale, categories = scales[concept]
                dataset = await uow.repositories.datasets.create(DatasetInput(concept=concept, study=programs.studies[study]))
                records = [
                    DataRecordInput(
                        unit_id=units[record.item_uid],
                        value=value_for(record.value, scale, categories),
                        start=record.start,
                        end=record.end,
                        groups=[RecordGroup(id=replicate, code=record.replicate)] if record.replicate else None
                    )
                    for record in plan.datasets[key]
                ]
                errors = [
                    (record.item_uid, record.value, error)
                    for record, error in zip(plan.datasets[key], dataset.add_records(records, scale, categories, [replicate]))
                    if error
                ]
                if errors:
                    raise ValueError(f"{len(errors)} records of dataset {key} do not parse, e.g. {errors[:3]}")
                created[key] = dataset.id
                ids.records += len(records)
            if submission_time != DESIGN:
                program.get_study(programs.studies[study]).get_grouping(grouping_id=replicate).merge_dataset_scope(
                    list(created.values())
                )
            await uow.commit()
        ids.datasets.update(created)
        ids.created += len(created)
        write_mapping(ids)

    logger.info(f"Prepared datasets: {ids.created} created with {ids.records} records, {len(ids.datasets)} in all")
    return ids
