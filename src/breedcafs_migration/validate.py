"""
Validation of a migration run (README.md §8).

Compares what the extracted and curated files say should have been migrated with the mapping files written by the run
and with what is stored, read directly from the database (controls through the access control service):
  - every expected item, variety, field, layout, input, study, dataset and Person is mapped, and every mapped id is stored;
  - units have the expected subject, parents, germplasm and tree positions;
  - datasets have their study, variable or factor, and the expected number of records;
  - the records of each branch and leaf are on the unit of the item it was taken from, with its codes,
    and the records of what is in a BreedCAFS block, or was taken from one, have the block's code;
  - the samples left out are listed, with their records, in unmigrated_samples.csv;
  - curve data files are stored and match the hash recorded for archival;
  - Persons have the curated names and institutions, and each dataset has the Persons who recorded it as contributors;
  - the migrated fields, sample locations, layouts, germplasm created from BreedCAFS, units, studies, datasets,
    curve data files and Persons are controlled by the migration team alone, and `PRIVATE`.

Writes validation_report.md to the data directory.
Run it after the migration as the migration user (main.py validate); it reads only.
"""
import csv
import hashlib
from dataclasses import dataclass, field
from pathlib import Path

from breedgraph.adapters.neo4j import Neo4jUnitOfWorkFactory
from breedgraph.domain.model.controls import ControlledModelLabel, ReadRelease
from breedgraph.domain.model.ontology import OntologyEntryLabel
from breedgraph.service_layer.infrastructure import archival_service

from breedcafs_migration.curves import planned_curves

from breedcafs_migration.bootstrap import MigrationContext
from breedcafs_migration.datasets import DatasetPlan, replicate_code
from breedcafs_migration.layouts import planned_layouts, ROW_AND_TREE
from breedcafs_migration.locations import read_fields, read_sample_locations
from breedcafs_migration.ontology import OntologyIds, DESIGN_FACTORS, RECORD_GROUP_TYPES
from breedcafs_migration.persons import read_persons, contributor_names
from breedcafs_migration.programs import STUDIES, CODE_GROUPINGS
from breedcafs_migration.setup.config import BREEDCAFS_DATA_DIR
from breedcafs_migration.units import UnitPlan, read_items, SUBJECTS
from breedcafs_migration.germplasm import read_varieties
from breedcafs_migration.writes import models_with_extra_stamps

import logging
logger = logging.getLogger(__name__)

BATCH = 5000


@dataclass
class Check:
    name: str
    passed: bool
    detail: str = ''


@dataclass
class Section:
    """A table in the report for reading, not checked"""
    title: str
    note: str
    header: list[str]
    rows: list[list]


@dataclass
class Validation:
    checks: list[Check] = field(default_factory=list)
    sections: list[Section] = field(default_factory=list)

    def check(self, name: str, passed: bool, detail: str = '') -> None:
        self.checks.append(Check(name, passed, detail))
        (logger.info if passed else logger.error)(f"{'PASS' if passed else 'FAIL'} {name} {detail}")

    def same(self, name: str, expected, actual) -> None:
        """Compares two collections, reporting counts and a few differences"""
        expected, actual = set(expected), set(actual)
        missing, extra = sorted(expected - actual, key=str), sorted(actual - expected, key=str)
        detail = f"{len(actual)} of {len(expected)}"
        if missing:
            detail += f"; missing {len(missing)}, e.g. {missing[:3]}"
        if extra:
            detail += f"; unexpected {len(extra)}, e.g. {extra[:3]}"
        self.check(name, not missing and not extra, detail)

    def all(self, name: str, problems: list, total: int) -> None:
        self.check(name, not problems, f"{total - len(problems)} of {total}" + (f"; e.g. {problems[:3]}" if problems else ''))

    @property
    def passed(self) -> bool:
        return all(check.passed for check in self.checks)


def read_mapping(name: str) -> list[dict[str, str]]:
    path = BREEDCAFS_DATA_DIR / name
    if not path.exists():
        return []
    with open(path) as f:
        return list(csv.DictReader(f))


def batches(values: list, size: int = BATCH):
    for start in range(0, len(values), size):
        yield values[start:start + size]


async def query(uow_factory, cypher: str, **parameters) -> list[dict]:
    async with uow_factory.get_uow() as uow:
        result = await uow.tx.run(cypher, **parameters)
        return [record.data() async for record in result]


async def stored_ids(uow_factory, label: str, ids: list[int]) -> set[int]:
    found = set()
    for batch in batches(ids):
        rows = await query(uow_factory, f"MATCH (n:{label}) WHERE n.id IN $ids RETURN n.id AS id", ids=batch)
        found.update(row['id'] for row in rows)
    return found


async def validate_controls(validation, uow_factory, context, label: ControlledModelLabel, ids: list[int], release: ReadRelease):
    problems = []
    async with uow_factory.get_uow(user_id=context.user_id) as uow:
        for batch in batches(ids):
            controllers = await uow.controls.get_controllers(label, batch)
            for model_id in batch:
                controller = controllers.get(model_id)
                teams = set(controller.controls) if controller else set()
                releases = {control.release for control in controller.controls.values()} if controller else set()
                if teams != {context.team_id} or releases != {release}:
                    problems.append((model_id, sorted(teams), sorted(r.name for r in releases)))
    validation.all(f"{label.value} controlled by the migration team, {release.name}", problems, len(ids))


async def validate_units(validation, uow_factory, ontology_subjects: dict[str, int]):
    plan = UnitPlan(read_items())
    expected = {uid for uid in plan.items if plan.is_unit(uid)}
    unit_ids = {row['item_uid']: int(row['unit_id']) for row in read_mapping('unit_ids.csv')}
    validation.same("Items mapped to units (unit_ids.csv)", expected, unit_ids)
    unmigrated = {row['item_uid']: row['reason'] for row in read_mapping('unmigrated_samples.csv')}
    validation.same("Samples left out, listed with their records (unmigrated_samples.csv)", plan.left_out.items(), unmigrated.items())

    germplasm = {row['variety']: int(row['germplasm_id']) for row in read_mapping('germplasm_ids.csv')}
    layouts = {(row['field_uid'], row['group'], row['layout_type']): int(row['layout_id']) for row in read_mapping('layout_ids.csv')}
    stored = {}
    for batch in batches(list(unit_ids.values())):
        for row in await query(uow_factory, """
            MATCH (u:Unit) WHERE u.id IN $ids
            RETURN u.id AS id,
                   [(u)-[:OF_SUBJECT]->(s) | s.id][0] AS subject,
                   [(u)-[:OF_GERMPLASM]->(g) | g.id][0] AS germplasm,
                   [(p:Unit)-[:INCLUDES_UNIT]->(u) | p.id] AS parents,
                   [(u)-[:IN_POSITION]->(position) | {
                       layout: [(position)-[:IN_LAYOUT]->(l) | l.id][0], coordinates: position.coordinates
                   }] AS positions
        """, ids=batch):
            stored[row['id']] = row
    validation.same("Units stored", unit_ids.values(), stored)

    subjects, parents, germplasm_problems, positions = [], [], [], []
    for uid, unit_id in unit_ids.items():
        unit, item = stored.get(unit_id), plan.items.get(uid)
        if unit is None or item is None:
            continue
        if unit['subject'] != ontology_subjects.get(SUBJECTS[item.subject]):
            subjects.append(uid)
        if uid != item.field_uid and set(unit['parents']) != {unit_ids.get(p) for p in plan.parents(item)}:
            parents.append(uid)
        variety = plan.germplasm_variety(item)
        if unit['germplasm'] != (germplasm.get(variety) if variety else None):
            germplasm_problems.append(uid)
        if uid in plan.tree_positions:
            group, row, tree = plan.tree_positions[uid]
            expected_position = {'layout': layouts.get((item.field_uid, group, ROW_AND_TREE)), 'coordinates': [row, tree]}
            if expected_position not in unit['positions']:
                positions.append(uid)
    validation.all("Units have their subject", subjects, len(unit_ids))
    validation.all("Units have their parents", parents, len(unit_ids))
    validation.all("Units have their germplasm", germplasm_problems, len(unit_ids))
    validation.all("Trees are positioned in their layout", positions, len(plan.tree_positions))
    return list(unit_ids.values())


async def validate_datasets(validation, uow_factory, ontology: OntologyIds):
    plan = DatasetPlan(ontology)
    plan.read_records()
    plan.read_factor_records()
    studies = {row['study']: int(row['study_id']) for row in read_mapping('study_ids.csv')}
    validation.same("Studies mapped (study_ids.csv)", STUDIES, studies)

    mapped = {
        (row['study'], int(row['concept_id']), row['submission_time'], row['submitter_id']): int(row['dataset_id'])
        for row in read_mapping('dataset_ids.csv')
    }
    validation.same("Datasets mapped (dataset_ids.csv)", plan.datasets, mapped)
    stored = {}
    for batch in batches(list(mapped.values())):
        for row in await query(uow_factory, """
            MATCH (d:Dataset) WHERE d.id IN $ids
            RETURN d.id AS id,
                   [(d)-[:FOR_STUDY]->(s) | s.id][0] AS study,
                   [(d)-[:FOR_CONCEPT]->(c) | c.id][0] AS concept,
                   COUNT { (d)-[:INCLUDES_RECORD]->(:Record) } AS records
        """, ids=batch):
            stored[row['id']] = row
    validation.same("Datasets stored", mapped.values(), stored)
    counts, placement = [], []
    for key, dataset_id in mapped.items():
        dataset = stored.get(dataset_id)
        if dataset is None or key not in plan.datasets:
            continue
        if dataset['records'] != len(plan.datasets[key]):
            counts.append((key, dataset['records'], len(plan.datasets[key])))
        if (dataset['study'], dataset['concept']) != (studies.get(key[0]), key[1]):
            placement.append(key)
    validation.all("Datasets have the expected number of records", counts, len(mapped))
    validation.all("Datasets are in their study, for their variable or factor", placement, len(mapped))
    expected_records = sum(len(records) for records in plan.datasets.values())
    stored_records = sum(dataset['records'] for dataset in stored.values())
    validation.check("Records stored", stored_records == expected_records, f"{stored_records} of {expected_records}")

    replicate_groupings = [int(row['replicate_grouping_id']) for row in read_mapping('study_ids.csv')]
    zero, = await query(uow_factory, """
        MATCH (g:RecordGrouping)-[:HAS_GROUP]->(:RecordGroup {code: '0'})<-[:IN_GROUP]-(record:Record)
        WHERE g.id IN $ids
        RETURN count(record) AS records
    """, ids=replicate_groupings)
    validation.check(
        "No record has replicate code 0, BreedCAFS's code for a reading not replicated",
        zero['records'] == 0, f"{zero['records']} with code 0"
    )
    await validate_record_codes(validation, uow_factory, plan)
    validation.sections.append(replicate_summary(plan, ontology))
    return mapped, list(studies.values())


async def validate_record_codes(validation, uow_factory, plan: DatasetPlan):
    """
    The records of each branch and leaf are on the unit of the item it was taken from, with its codes (README §6.1),
    and the records of what is in a BreedCAFS block, or was taken from one, have the block's code (README §6.4):
    compared as the number of records with each code on each unit, for each code grouping.
    """
    unit_ids = {row['item_uid']: int(row['unit_id']) for row in read_mapping('unit_ids.csv')}
    rows = read_mapping('study_ids.csv')
    expected: dict[tuple[str, str, int | None], int] = {}
    for records in plan.datasets.values():
        for record in records:
            for name, code in record.codes.items():
                key = (name, code, unit_ids.get(record.item_uid))
                expected[key] = expected.get(key, 0) + 1
    for name in CODE_GROUPINGS:
        column = f'{name.lower()}_grouping_id'
        stored = {
            (name, row['code'], row['unit']): row['records']
            for row in await query(uow_factory, """
                MATCH (grouping:RecordGrouping)-[:HAS_GROUP]->(group:RecordGroup)<-[:IN_GROUP]-(record:Record)-[:FOR_UNIT]->(unit:Unit)
                WHERE grouping.id IN $ids
                RETURN group.code AS code, unit.id AS unit, count(record) AS records
            """, ids=[int(row[column]) for row in rows if row.get(column)])
        }
        planned = {key: count for key, count in expected.items() if key[0] == name}
        validation.same(f"{name} codes on units", planned, stored)
        validation.all(
            f"Records with each {name} code on each unit",
            [key for key, count in planned.items() if key in stored and stored[key] != count], len(planned)
        )


async def validate_curves(validation, uow_factory, ontology: OntologyIds):
    planned, _ = planned_curves(ontology)
    rows = read_mapping('curve_ids.csv')
    mapped = {
        (row['study'], int(row['concept_id']), row['submission_time'], row['submitter_id']): (int(row['reference_id']), int(row['dataset_id']))
        for row in rows
    }
    validation.same("Curve datasets mapped (curve_ids.csv)", planned, mapped)
    storage = Path(archival_service.FILE_STORAGE_PATH)
    problems = []
    for key, (reference_id, dataset_id) in mapped.items():
        found = await query(uow_factory, """
            MATCH (d:Dataset {id: $dataset})<-[:REFERENCE_FOR]-(f:Reference {id: $reference})
            OPTIONAL MATCH (a:FileArchiveRecord)-[:FOR_REFERENCE]->(f)
            RETURN COUNT { (d)-[:INCLUDES_RECORD]->(:Record) } AS records,
                   COUNT { (d)-[:INCLUDES_RECORD]->(r:Record)<-[:REFERENCE_FOR]-(f) } AS referencing,
                   f.file_id AS file_id, a.file_hash AS hash
        """, dataset=dataset_id, reference=reference_id)
        if not found:
            problems.append((dataset_id, "dataset or its data file reference not stored"))
            continue
        found, expected = found[0], len(planned.get(key, []))
        path = storage / (found['file_id'] or '')
        if found['records'] != expected or found['referencing'] != expected:
            problems.append((dataset_id, f"{found['records']} curves, {found['referencing']} referencing the file, of {expected}"))
        elif not path.is_file() or hashlib.sha256(path.read_bytes()).hexdigest() != found['hash']:
            problems.append((dataset_id, "file missing or not matching its archival hash"))
    validation.all("Curve datasets have their curves and stored data file", problems, len(mapped))
    return {key: dataset_id for key, (_, dataset_id) in mapped.items()}, [reference_id for reference_id, _ in mapped.values()]


async def validate_persons(validation, uow_factory, ontology: OntologyIds, datasets: dict):
    persons = read_persons()
    mapped = {(row['Name'], row['institution']): int(row['person_id']) for row in read_mapping('person_ids.csv')}
    validation.same("Persons mapped (person_ids.csv)", persons.values(), mapped)
    rows = await query(uow_factory, "MATCH (p:Person) WHERE p.id IN $ids RETURN p.id AS id, p.name AS name, p.institution AS institution",
                       ids=list(mapped.values()))
    validation.same("Persons stored with their name and institution", mapped,
                    [(row['name'], row['institution'] or '') for row in rows])

    expected = {
        dataset_id: {mapped.get(persons.get(name)) for name in names}
        for dataset_id, names in contributor_names(ontology, datasets).items()
    }
    stored = {}
    for batch in batches(list(datasets.values())):
        for row in await query(uow_factory, """
            MATCH (d:Dataset) WHERE d.id IN $ids RETURN d.id AS id, [(p:Person)-[:CONTRIBUTED_TO]->(d) | p.id] AS contributors
        """, ids=batch):
            stored[row['id']] = set(row['contributors'])
    problems = [
        (dataset_id, sorted(stored.get(dataset_id, set())), sorted(contributors, key=str))
        for dataset_id, contributors in expected.items() if stored.get(dataset_id, set()) != contributors
    ]
    validation.all("Datasets have the Persons who recorded them as contributors", problems, len(expected))
    return list(mapped.values())


async def validate_ontology(validation, uow_factory, context) -> tuple[OntologyIds, dict[str, int]]:
    ontology = OntologyIds()
    for row in read_mapping('ontology_ids.csv'):
        ontology.inputs[(row['input'], row['apparatus'])] = (OntologyEntryLabel(row['label']), int(row['id']))
    problems = []
    for label in {label for label, _ in ontology.inputs.values()}:
        ids = [entry_id for entry_label, entry_id in ontology.inputs.values() if entry_label == label]
        stored = await stored_ids(uow_factory, label.value, ids)
        problems += [(key, entry_id) for key, (entry_label, entry_id) in ontology.inputs.items() if entry_label == label and entry_id not in stored]
    validation.all("Inputs mapped to stored variables and factors (ontology_ids.csv)", problems, len(ontology.inputs))
    subjects = {}
    async with uow_factory.get_uow(user_id=context.user_id) as uow:
        for factor in DESIGN_FACTORS:
            entry = await uow.ontology.get_entry(name=factor['Factor'], label=OntologyEntryLabel.FACTOR)
            if entry is not None:
                ontology.design_factors[factor['Factor']] = entry.id
        for name in set(SUBJECTS.values()):
            entry = await uow.ontology.get_entry(name=name, label=OntologyEntryLabel.SUBJECT)
            if entry is not None:
                subjects[name] = entry.id
        extents = {}
        for name, _, _ in RECORD_GROUP_TYPES:
            entry = await uow.ontology.get_entry(name=name, label=OntologyEntryLabel.RECORD_GROUP_TYPE)
            if entry is not None:
                extents[name] = entry.extent
    validation.same("Design factors in the ontology", [f['Factor'] for f in DESIGN_FACTORS], ontology.design_factors)
    validation.same("Subjects in the ontology", set(SUBJECTS.values()), subjects)
    validation.same(
        "Record group types in the ontology, with their extents",
        {(name, extent.value) for name, _, extent in RECORD_GROUP_TYPES},
        {(name, extent.value) for name, extent in extents.items()}
    )
    return ontology, subjects


async def validate_locations_and_layouts(validation, uow_factory):
    fields = {row['field_uid']: int(row['location_id']) for row in read_mapping('location_ids.csv')}
    validation.same("Fields mapped to locations (location_ids.csv)", [row['field_uid'] for row in read_fields()], fields)
    sample_locations = {row['location']: int(row['location_id']) for row in read_mapping('sample_location_ids.csv')}
    validation.same("Sample locations mapped (sample_location_ids.csv)", read_sample_locations(), sample_locations)
    location_ids = list(fields.values()) + list(sample_locations.values())
    validation.same("Locations stored", location_ids, await stored_ids(uow_factory, 'Location', location_ids))

    layouts = {(row['field_uid'], row['group'], row['layout_type']): int(row['layout_id']) for row in read_mapping('layout_ids.csv')}
    validation.same("Layouts mapped (layout_ids.csv)", planned_layouts(), layouts)
    validation.same("Layouts stored", layouts.values(), await stored_ids(uow_factory, 'Layout', list(layouts.values())))

    germplasm = {row['variety']: int(row['germplasm_id']) for row in read_mapping('germplasm_ids.csv')}
    validation.same("Varieties mapped to germplasm (germplasm_ids.csv)", read_varieties(), germplasm)
    validation.same("Germplasm stored", germplasm.values(), await stored_ids(uow_factory, 'Germplasm', list(germplasm.values())))
    created_germplasm = [int(row['germplasm_id']) for row in read_mapping('germplasm_ids.csv') if row['source'] == 'breedcafs']
    return location_ids, list(layouts.values()), created_germplasm


def write_report(validation: Validation) -> Path:
    path = BREEDCAFS_DATA_DIR / 'validation_report.md'
    with open(path, 'w') as f:
        f.write(f"# Migration validation: {'PASSED' if validation.passed else 'FAILED'}\n\n| Check | Result | Detail |\n|---|---|---|\n")
        for check in validation.checks:
            f.write(f"| {check.name} | {'pass' if check.passed else 'FAIL'} | {check.detail.replace('|', '/')} |\n")
        for section in validation.sections:
            f.write(f"\n## {section.title}\n\n{section.note}\n\n| {' | '.join(section.header)} |\n")
            f.write(f"|{'---|' * len(section.header)}\n")
            for row in section.rows:
                f.write(f"| {' | '.join(str(value).replace('|', '/') for value in row)} |\n")
    return path


def replicate_summary(plan: DatasetPlan, ontology: OntologyIds) -> Section:
    """
    The replicate codes migrated for each input, after code 0 is dropped (README §7.6), for auditing:
    records, records with a code, readings (same submission, unit and time) with several replicates,
    the most replicates in a reading, and the range of codes.
    """
    names = {}
    for (input_name, apparatus), (_, concept_id) in ontology.inputs.items():
        names.setdefault(concept_id, set()).add(f"{input_name} ({apparatus})" if apparatus else input_name)
    by_concept: dict[int, list] = {}
    for (study, concept_id, submission_time, submitter_id), records in plan.datasets.items():
        for record in records:
            by_concept.setdefault(concept_id, []).append(((study, submission_time, submitter_id), record))
    rows = []
    for concept_id, entries in by_concept.items():
        coded = [(submission, r) for submission, r in entries if replicate_code(r.replicate)]
        readings: dict[tuple, list[str]] = {}
        for submission, r in coded:
            readings.setdefault((submission, r.item_uid, r.sample, r.start, r.end), []).append(replicate_code(r.replicate))
        replicated = [codes for codes in readings.values() if len(codes) > 1]
        numbers = sorted({int(c) for codes in readings.values() for c in codes if c.isdigit()})
        rows.append([
            ', '.join(sorted(names.get(concept_id, {str(concept_id)}))), len(entries), len(coded), len(replicated),
            max((len(codes) for codes in readings.values()), default=0),
            f"{numbers[0]}–{numbers[-1]}" if numbers else ''
        ])
    rows.sort(key=lambda row: (-row[2], row[0]))
    return Section(
        title="Replicate codes by input",
        note=(
            "What was migrated for each input, code 0 having been dropped (README §7.6). A reading is the records of one "
            "submission, unit and time; replicates recorded minutes apart are separate readings here, and are combined "
            "in analysis with a replicate aggregation window."
        ),
        header=["Input", "Records", "With a code", "Readings with several replicates", "Most in a reading", "Codes"],
        rows=rows
    )


async def validate_breedcafs_migration(uow_factory: Neo4jUnitOfWorkFactory, context: MigrationContext) -> Validation:
    validation = Validation()
    ontology, subjects = await validate_ontology(validation, uow_factory, context)
    locations, layouts, germplasm = await validate_locations_and_layouts(validation, uow_factory)
    units = await validate_units(validation, uow_factory, subjects)
    datasets, studies = await validate_datasets(validation, uow_factory, ontology)
    curve_datasets, references = await validate_curves(validation, uow_factory, ontology)
    persons = await validate_persons(validation, uow_factory, ontology, {**datasets, **curve_datasets})

    private = ReadRelease.PRIVATE
    for label, ids in (
            (ControlledModelLabel.LOCATION, locations),
            (ControlledModelLabel.LAYOUT, layouts),
            (ControlledModelLabel.GERMPLASM, germplasm),
            (ControlledModelLabel.UNIT, units),
            (ControlledModelLabel.STUDY, studies),
            (ControlledModelLabel.DATASET, [*datasets.values(), *curve_datasets.values()]),
            (ControlledModelLabel.REFERENCE, references),
            (ControlledModelLabel.PERSON, persons),
    ):
        await validate_controls(validation, uow_factory, context, label, ids, private)

    extra = await models_with_extra_stamps(uow_factory, context.user_id)
    validation.all(
        "Models with one write stamp by the migration user (README §14), by label",
        [(label.value, models) for label, models in extra.items() if models], len(extra)
    )

    path = write_report(validation)
    failed = [check.name for check in validation.checks if not check.passed]
    logger.info(f"Validation {'passed' if not failed else 'failed'}: {len(validation.checks) - len(failed)} of "
                f"{len(validation.checks)} checks passed; report in {path}")
    return validation
