"""
Persons, and the contributors of the migrated datasets (README.md §7.6, 1_7_Extract_Persons.md).

Each row of persons.csv becomes a Person with its name and institution, `PRIVATE` and controlled by the migration team,
whose team tree's legal entity (the University of Galway) is the data controller, so the basis is public task.
The informed attestation is given by the migration administrator. Persons are matched by name and institution,
so running this again creates nothing new.

A dataset's contributors are the Persons who recorded its records: the attribution values (the BreedCAFS record
`person`, or the submitter where none was given) of its submission for its input, in submissions.csv,
mapped to Persons by attribution_persons.csv. A submission's attribution values are not split by study,
so a submission covering two studies credits the same Persons in both.
The factor datasets of the block treatments are not from a submission, so have no contributors.

Writes person_ids.csv, mapping each Person's name and institution to its id.
"""
import csv
from dataclasses import dataclass, field

from breedgraph.adapters.neo4j import Neo4jUnitOfWorkFactory
from breedgraph.domain.model.people import PersonInput, LawfulBasis

from breedcafs_migration.bootstrap import MigrationContext, MigrationSettingsError
from breedcafs_migration.curves import CurveIds
from breedcafs_migration.datasets import DatasetIds, DatasetKey
from breedcafs_migration.ontology import OntologyIds
from breedcafs_migration.setup.config import BREEDCAFS_DATA_DIR

import logging
logger = logging.getLogger(__name__)

# (name, institution)
PersonKey = tuple[str, str]


@dataclass
class PersonIds:
    persons: dict[PersonKey, int] = field(default_factory=dict)
    created: int = 0
    # dataset id -> person ids
    contributors: dict[int, list[int]] = field(default_factory=dict)


def read_csv(name: str) -> list[dict[str, str]]:
    with open(BREEDCAFS_DATA_DIR / name, encoding='utf-8-sig') as f:
        return list(csv.DictReader(f))


def names_in(value: str) -> list[str]:
    return [name.strip() for name in (value or '').split(';') if name.strip()]


def read_persons() -> dict[str, PersonKey]:
    """Persons by name, which identifies them in attribution_persons.csv"""
    persons = {}
    for row in read_csv('persons.csv'):
        name = row['Name'].strip()
        if name in persons:
            raise ValueError(f"persons.csv names a Person twice: {name}")
        persons[name] = (name, row['institution'].strip())
    return persons


def contributor_names(ontology: OntologyIds, datasets: dict[DatasetKey, int]) -> dict[int, set[str]]:
    """The names of the Persons who recorded each dataset's records"""
    inputs_of: dict[int, set[str]] = {}
    for (input_name, _), (_, concept) in ontology.inputs.items():
        inputs_of.setdefault(concept, set()).add(input_name)
    names_of = {(row['attribution'], row['partner']): names_in(row['Name']) for row in read_csv('attribution_persons.csv')}
    attributions: dict[tuple[str, str, str], set[tuple[str, str]]] = {}
    for row in read_csv('submissions.csv'):
        attributions.setdefault((row['submission_time'], row['submitter_id'], row['input']), set()).add(
            (row['attribution'], row['partner'])
        )
    contributors = {}
    for (_, concept, submission_time, submitter_id), dataset_id in datasets.items():
        names = set()
        for input_name in inputs_of.get(concept, ()):
            for attribution in attributions.get((submission_time, submitter_id, input_name), ()):
                names.update(names_of.get(attribution, ()))
        contributors[dataset_id] = names
    return contributors


async def create_persons(uow_factory: Neo4jUnitOfWorkFactory, context: MigrationContext, ids: PersonIds) -> None:
    persons = read_persons()
    async with uow_factory.get_uow(user_id=context.user_id, write_team=context.team_id) as uow:
        team_tree = await uow.repositories.team_trees.get(team_id=context.team_id)
        if team_tree is None or team_tree.legal_entity is None:
            raise MigrationSettingsError(
                "Recording Persons requires the migration team's team tree to have declared its legal entity"
            )
        for name, institution in persons.values():
            existing = [
                person async for person in uow.repositories.people.get_all(name=name)
                if (person.institution or '') == institution
            ]
            if existing:
                ids.persons[(name, institution)] = existing[0].id
                continue
            person = await uow.repositories.people.create(PersonInput(
                name=name,
                institution=institution or None,
                basis=LawfulBasis.PUBLIC_TASK,
                informed_attestation=True
            ))
            ids.persons[(name, institution)] = person.id
            ids.created += 1
        await uow.commit()


async def set_contributors(
        uow_factory: Neo4jUnitOfWorkFactory,
        context: MigrationContext,
        ids: PersonIds,
        contributors: dict[int, set[str]]
) -> None:
    persons = read_persons()
    unknown = sorted({name for names in contributors.values() for name in names} - set(persons))
    if unknown:
        raise ValueError(f"attribution_persons.csv names Persons not in persons.csv: {unknown}")
    dataset_ids = sorted(dataset_id for dataset_id, names in contributors.items() if names)
    batch = 100
    for start in range(0, len(dataset_ids), batch):
        async with uow_factory.get_uow(user_id=context.user_id) as uow:
            for dataset_id in dataset_ids[start:start + batch]:
                person_ids = sorted(ids.persons[persons[name]] for name in contributors[dataset_id])
                dataset = await uow.repositories.datasets.get(dataset_id=dataset_id)
                if sorted(dataset.contributors) != person_ids:
                    dataset.contributors = person_ids
                ids.contributors[dataset_id] = person_ids
            await uow.commit()


def write_mapping(ids: PersonIds) -> None:
    with open(BREEDCAFS_DATA_DIR / 'person_ids.csv', 'w', newline='') as f:
        writer = csv.writer(f)
        writer.writerow(['Name', 'institution', 'person_id'])
        for (name, institution), person_id in sorted(ids.persons.items()):
            writer.writerow([name, institution, person_id])


async def prepare_breedcafs_persons(
        uow_factory: Neo4jUnitOfWorkFactory,
        context: MigrationContext,
        ontology: OntologyIds,
        datasets: DatasetIds,
        curves: CurveIds
) -> PersonIds:
    ids = PersonIds()
    await create_persons(uow_factory, context, ids)
    write_mapping(ids)
    all_datasets = {**datasets.datasets, **{key: dataset_id for key, (_, dataset_id) in curves.datasets.items()}}
    contributors = contributor_names(ontology, all_datasets)
    await set_contributors(uow_factory, context, ids, contributors)
    logger.info(
        f"Prepared Persons: {ids.created} of {len(ids.persons)} created; "
        f"contributors set on {len(ids.contributors)} of {len(all_datasets)} datasets"
    )
    return ids
