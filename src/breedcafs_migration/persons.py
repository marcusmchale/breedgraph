"""
Persons, and the contributors of the migrated datasets (README.md §7.6, 1_7_Extract_Persons.md).

Each row of persons.csv becomes a Person with its name and institution, `PRIVATE` and controlled by the migration team.
The University of Galway is the data controller of every Person in BreedGraph (docs/person.md §2).
The consent attestation is given by the migration administrator, who has the consent of every person in persons.csv
(RUNBOOK §2). Persons are matched by name and institution,
so running this again creates nothing new.

A dataset credits the Persons who recorded its records, without roles: the attribution values (the BreedCAFS record
`person`, or the submitter where none was given) of its submission for its input, in submissions.csv,
mapped to Persons by attribution_persons.csv. A submission's attribution values are not split by study,
so a submission covering two studies credits the same Persons in both.
It also credits its submitter with the Data curation role, mapped to a Person by submitter_persons.csv
(docs/contributions.md §7). A submitter who also recorded the data has one contribution, with Data curation.
The factor datasets of the block treatments are not from a submission, so credit no one.

Writes person_ids.csv, mapping each Person's name and institution to its id.

    python -m breedcafs_migration.persons --draft-submitters   # writes submitter_persons.csv to curate, if absent
"""
import argparse
import csv
from dataclasses import dataclass, field

from breedgraph.domain.model.contributions import Contribution
from breedgraph.adapters.neo4j import Neo4jUnitOfWorkFactory
from breedgraph.service_layer.application.ontology_seed import credit_seed_key_for
from breedgraph.domain.model.people import PersonInput

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
    # dataset id -> (person id, role ids), by person id
    contributions: dict[int, list[tuple[int, tuple[int, ...]]]] = field(default_factory=dict)


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


SUBMITTER_PERSONS = 'submitter_persons.csv'
DATA_CURATION = 'Data curation'


def draft_submitter_persons() -> bool:
    """
    Write submitter_persons.csv for curation, one row per submitter and Partner in submissions.csv, unless it exists.
    Name is suggested from the submitter's fallback attribution ("submitter: <user name>") in attribution_persons.csv.
    """
    path = BREEDCAFS_DATA_DIR / SUBMITTER_PERSONS
    if path.exists():
        return False
    suggested = {(row['attribution'], row['partner']): row['Name'] for row in read_csv('attribution_persons.csv')}
    submitters = {}
    for row in read_csv('submissions.csv'):
        if row['submitter_id']:
            submitters[(row['submitter_id'], row['partner'])] = row['submitter']
    with open(path, 'w', newline='', encoding='utf-8') as f:
        writer = csv.writer(f)
        writer.writerow(['submitter_id', 'submitter', 'partner', 'Name'])
        for (submitter_id, partner), submitter in sorted(submitters.items()):
            writer.writerow([submitter_id, submitter, partner, suggested.get((f'submitter: {submitter}', partner), '')])
    return True


def read_submitter_persons() -> dict[str, list[str]]:
    """The names of the Persons each submitter is, by BreedCAFS node id; empty to leave a submitter uncredited"""
    if not (BREEDCAFS_DATA_DIR / SUBMITTER_PERSONS).exists():
        raise MigrationSettingsError(
            f"{SUBMITTER_PERSONS} is missing: draft it with `python -m breedcafs_migration.persons --draft-submitters`, "
            "then curate it (1_7_Extract_Persons.md)"
        )
    return {row['submitter_id']: names_in(row['Name']) for row in read_csv(SUBMITTER_PERSONS)}


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


def curator_names(datasets: dict[DatasetKey, int]) -> dict[int, set[str]]:
    """The names of the Persons who submitted each dataset's records, to be credited with Data curation"""
    submitter_persons = read_submitter_persons()
    return {
        dataset_id: set(submitter_persons.get(submitter_id, ())) if submitter_id else set()
        for (_, _, _, submitter_id), dataset_id in datasets.items()
    }


def contribution_names(ontology: OntologyIds, datasets: dict[DatasetKey, int]) -> dict[int, dict[str, bool]]:
    """Each dataset's credited Persons by name, and whether they are credited with Data curation"""
    recorders = contributor_names(ontology, datasets)
    curators = curator_names(datasets)
    return {
        dataset_id: {**{name: False for name in recorders[dataset_id]}, **{name: True for name in curators[dataset_id]}}
        for dataset_id in datasets.values()
    }


async def create_persons(uow_factory: Neo4jUnitOfWorkFactory, context: MigrationContext, ids: PersonIds) -> None:
    persons = read_persons()
    async with uow_factory.get_uow(user_id=context.user_id, write_team=context.team_id) as uow:
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
                consent_attestation=True
            ))
            ids.persons[(name, institution)] = person.id
            ids.created += 1
        await uow.commit()


async def set_contributions(
        uow_factory: Neo4jUnitOfWorkFactory,
        context: MigrationContext,
        ids: PersonIds,
        contributions: dict[int, dict[str, bool]]
) -> None:
    persons = read_persons()
    unknown = sorted({name for names in contributions.values() for name in names} - set(persons))
    if unknown:
        raise ValueError(f"attribution_persons.csv or {SUBMITTER_PERSONS} names Persons not in persons.csv: {unknown}")
    async with uow_factory.get_uow(user_id=context.user_id) as uow:
        curation = await uow.ontology.get_seeded_entry(credit_seed_key_for(DATA_CURATION))
        if curation is None:
            raise MigrationSettingsError(f"The {DATA_CURATION} Role is seeded by setup_initial_data.py, but is missing")
    dataset_ids = sorted(dataset_id for dataset_id, names in contributions.items() if names)
    batch = 100
    for start in range(0, len(dataset_ids), batch):
        async with uow_factory.get_uow(user_id=context.user_id) as uow:
            for dataset_id in dataset_ids[start:start + batch]:
                credited = sorted(
                    (ids.persons[persons[name]], (curation.id,) if curator else ())
                    for name, curator in contributions[dataset_id].items()
                )
                dataset = await uow.repositories.datasets.get(dataset_id=dataset_id)
                stored = sorted((contribution.person, tuple(contribution.roles)) for contribution in dataset.contributions)
                if stored != credited:
                    dataset.contributions = [Contribution(person=person_id, roles=list(roles)) for person_id, roles in credited]
                ids.contributions[dataset_id] = credited
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
    contributions = contribution_names(ontology, all_datasets)
    await set_contributions(uow_factory, context, ids, contributions)
    logger.info(
        f"Prepared Persons: {ids.created} of {len(ids.persons)} created; "
        f"contributions set on {len(ids.contributions)} of {len(all_datasets)} datasets"
    )
    return ids


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Curation files for the migrated Persons")
    parser.add_argument('--draft-submitters', action='store_true', help=f"write {SUBMITTER_PERSONS} to curate, if absent")
    if parser.parse_args().draft_submitters:
        logging.basicConfig(level=logging.INFO)
        if draft_submitter_persons():
            logger.info(f"Wrote {SUBMITTER_PERSONS}: fill in or check each Name, and add any new Persons to persons.csv")
        else:
            logger.info(f"{SUBMITTER_PERSONS} exists, so was left as it is")
