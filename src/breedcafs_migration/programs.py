"""
The BreedCAFS program, its trials and studies (README.md §7.5).

One BreedCAFS program, with trials by the kind of data and studies by where it was recorded (STUDIES).
Each study has a dataset-scoped Replicate grouping, scoped in the datasets phase to the datasets of each submission
(README §7.6), so replicate codes are only compared within the records submitted together.
The studies with records of branches (Nicaragua and Vietnam) also have study-wide Branch and Stratum groupings,
for the branch each record was taken from and its stratum, as branches are not units (README §6.1).
study_for gives the study a record belongs to.
Each study's start and end are the first and last times of its records (records.csv and curves.csv):
record times, and condition start and end times where given.

The program, trials, studies and groupings are matched by name, or created, `PRIVATE` and controlled by the migration team,
so running this again creates nothing new.
Writes study_ids.csv, mapping each study to its id and the ids of its Replicate, Branch and Stratum groupings.
"""
import csv
import json
from dataclasses import dataclass, field

from numpy import datetime64

from breedgraph.adapters.neo4j import Neo4jUnitOfWorkFactory
from breedgraph.domain.model.programs import (
    ProgramInput, TrialInput, StudyInput, RecordGroupingInput, RecordGroupingStored, GroupingScope
)

from breedcafs_migration.bootstrap import MigrationContext
from breedcafs_migration.setup.config import BREEDCAFS_DATA_DIR
from breedcafs_migration.units import read_items, BRANCH

import logging
logger = logging.getLogger(__name__)

PROGRAM = ProgramInput(
    name="BreedCAFS",
    fullname="Breeding Coffee for Agroforestry Systems",
    description="Data migrated from the BreedCAFS project database"
)
# Trial name -> description
TRIALS = {
    "Field trials": "Observations of trees, and samples from them, in field trials",
    "Controlled environment": "Observations of trees, and samples from them, grown in controlled environments",
    "Sample analyses": "Laboratory analyses of samples from the field trials",
}
# Study key -> trial name, study name, description
STUDIES = {
    "Cameroon": ("Field trials", "Cameroon", "BreedCAFS field trials in Cameroon"),
    "Costa Rica": ("Field trials", "Costa Rica", "BreedCAFS field trials in Costa Rica"),
    "French Guiana": ("Field trials", "French Guiana", "BreedCAFS field trials in French Guiana"),
    "Nicaragua": ("Field trials", "Nicaragua", "BreedCAFS field trials in Nicaragua"),
    "Vietnam": ("Field trials", "Vietnam", "BreedCAFS field trials in Vietnam"),
    "Denmark": ("Controlled environment", "Denmark", "BreedCAFS greenhouse trials in Copenhagen"),
    "Metabolomics": ("Sample analyses", "Metabolomics (IRD)", "Metabolite analysis of BreedCAFS samples (IRD)"),
    "Mineral analysis": ("Sample analyses", "Mineral analysis", "Mineral analysis of BreedCAFS samples"),
}
# Terms of inputs whose records belong to a sample analysis study, whatever the country
TERM_STUDIES = {
    "Metabolites": "Metabolomics",
    "Elements": "Mineral analysis",
}
REPLICATE = "Replicate"
STRATUM = "Stratum"
# Study-wide groupings of the studies with records of branches
BRANCH_GROUPINGS = (BRANCH, STRATUM)


def study_for(terms: set[str], country: str) -> str:
    """The study a record belongs to, from the terms of its input and the country of its item's field"""
    for term, study in TERM_STUDIES.items():
        if term in terms:
            return study
    if country not in STUDIES:
        raise ValueError(f"No study is given for records from {country}")
    return country


def clean(value: str) -> str:
    """Values in the exported CSVs are wrapped in extra quotes"""
    return (value or '').strip().strip('"').strip()


def read_csv(name: str) -> list[dict[str, str]]:
    with open(BREEDCAFS_DATA_DIR / name, encoding='utf-8-sig') as f:
        return list(csv.DictReader(f))


def input_terms() -> dict[str, set[str]]:
    terms = {}
    for row in read_csv('input_details_curated.csv'):
        value = row['terms'].replace('“', '"').replace('”', '"').strip()
        terms[clean(row['name'])] = set(json.loads(value)) if value and value != 'null' else set()
    return terms


def field_countries() -> dict[str, str]:
    return {clean(row['field_uid']): clean(row['country']) for row in read_csv('field_farm_region_country.csv')}


def study_dates() -> dict[str, tuple[datetime64, datetime64]]:
    """The dates of the first and last record times of each study (BreedCAFS times are milliseconds since the epoch)"""
    terms = input_terms()
    countries = field_countries()
    times: dict[str, list[int]] = {}
    for name, columns in (('records.csv', ('time', 'start', 'end')), ('curves.csv', ('time',))):
        for row in read_csv(name):
            values = [int(row[column]) for column in columns if row[column].lstrip('-').isdigit()]
            if values:
                study = study_for(terms.get(row['input'], set()), countries[row['item_uid'].split('_')[0]])
                times.setdefault(study, []).extend(values)
    return {
        study: (datetime64(min(values), 'ms').astype('datetime64[D]'), datetime64(max(values), 'ms').astype('datetime64[D]'))
        for study, values in times.items()
    }


def branch_studies() -> set[str]:
    """The studies with records of branches"""
    branches = {uid for uid, item in read_items().items() if item.subject == BRANCH}
    terms = input_terms()
    countries = field_countries()
    return {
        study_for(terms.get(row['input'], set()), countries[row['item_uid'].split('_')[0]])
        for row in read_csv('records.csv') if row['item_uid'] in branches
    }


@dataclass
class ProgramIds:
    program_id: int | None = None
    trials: dict[str, int] = field(default_factory=dict)
    # Study key -> study id, and the ids of its Replicate grouping and of its Branch and Stratum groupings if it has them
    studies: dict[str, int] = field(default_factory=dict)
    replicate_groupings: dict[str, int] = field(default_factory=dict)
    branch_groupings: dict[str, int] = field(default_factory=dict)
    stratum_groupings: dict[str, int] = field(default_factory=dict)
    created: int = 0


def find_by_name(models, name: str):
    return next((model for model in models if model.name.casefold() == name.casefold()), None)


async def prepare_breedcafs_programs(
        uow_factory: Neo4jUnitOfWorkFactory,
        context: MigrationContext,
        record_group_types: dict[str, int]
) -> ProgramIds:
    ids = ProgramIds()
    dates = study_dates()
    with_branches = branch_studies()
    async with uow_factory.get_uow(user_id=context.user_id, write_team=context.team_id) as uow:
        programs = uow.repositories.programs
        program = await programs.get(name=PROGRAM.name)
        if program is None:
            program = await programs.create(PROGRAM)
            ids.created += 1

        for name, description in TRIALS.items():
            if find_by_name(program.trials.values(), name) is None:
                program.add_trial(TrialInput(name=name, description=description))
                ids.created += 1
        await programs.update_seen()

        for key, (trial_name, name, description) in STUDIES.items():
            trial = find_by_name(program.trials.values(), trial_name)
            study = find_by_name(trial.studies.values(), name)
            start, end = dates.get(key, (None, None))
            if study is None:
                trial.add_study(StudyInput(name=name, description=description, start=start, end=end, groupings=[
                    RecordGroupingInput(type=record_group_types[REPLICATE], name=REPLICATE, scope=GroupingScope.DATASET_SCOPED)
                ]))
                ids.created += 1
                study = find_by_name(trial.studies.values(), name)
            elif (study.start, study.end) != (start, end):
                study.start, study.end = start, end
            if key in with_branches:
                for grouping_name in BRANCH_GROUPINGS:
                    if study.get_grouping(name=grouping_name) is None:
                        study.add_grouping(record_group_types[grouping_name], grouping_name, GroupingScope.STUDY_WIDE)
                        ids.created += 1
        await programs.update_seen()

        ids.program_id = program.id
        for name in TRIALS:
            ids.trials[name] = find_by_name(program.trials.values(), name).id
        for key, (trial_name, name, _) in STUDIES.items():
            study = find_by_name(program.trials[ids.trials[trial_name]].studies.values(), name)
            grouping = study.get_grouping(name=REPLICATE)
            if not isinstance(grouping, RecordGroupingStored) or grouping.scope is not GroupingScope.DATASET_SCOPED:
                raise ValueError(f"The study {name} has no stored dataset-scoped {REPLICATE} grouping")
            ids.studies[key] = study.id
            ids.replicate_groupings[key] = grouping.id
            if key in with_branches:
                for grouping_name, grouping_ids in zip(BRANCH_GROUPINGS, (ids.branch_groupings, ids.stratum_groupings)):
                    grouping = study.get_grouping(name=grouping_name)
                    if not isinstance(grouping, RecordGroupingStored) or grouping.scope is not GroupingScope.STUDY_WIDE:
                        raise ValueError(f"The study {name} has no stored study-wide {grouping_name} grouping")
                    grouping_ids[key] = grouping.id
        await uow.commit()

    logger.info(f"Prepared the program: {ids.created} created, {len(ids.studies)} studies")
    write_study_mapping(ids)
    return ids


def write_study_mapping(ids: ProgramIds) -> None:
    with open(BREEDCAFS_DATA_DIR / 'study_ids.csv', 'w', newline='') as f:
        writer = csv.writer(f)
        writer.writerow(['study', 'study_id', 'replicate_grouping_id', 'branch_grouping_id', 'stratum_grouping_id'])
        for key, study_id in ids.studies.items():
            writer.writerow([
                key, study_id, ids.replicate_groupings[key], ids.branch_groupings.get(key, ''), ids.stratum_groupings.get(key, '')
            ])
