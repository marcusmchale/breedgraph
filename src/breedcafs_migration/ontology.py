"""
Prepare the ontology entries the migrated data needs (README.md §2 and 7, 1_5_Extract_Inputs.md).

Fixed entries: subjects, location types and layout types.
From input_details_curated.csv: terms, scales and their categories, observation and control methods,
traits and conditions, and the variables and factors each BreedCAFS input maps to.
Trait and condition subjects come from input_subjects.csv, the subjects each input has records for.

Entries are looked up by name first, so existing entries (e.g. in the production ontology) are used,
and running this again creates nothing new. Relationships are only added to entries created here.
The new entries are drafts until the ontology version is committed at the end.

Writes ontology_ids.csv, mapping each BreedCAFS input to the variable or factor it is recorded against.
Photosynthesis inputs map by input and apparatus, as Fᵥ / Fₘ was measured with two instruments:
a record's apparatus is the Photosynthetic Analysis Apparatus value for its item at the same time.
Writes ontology_entry_ids.csv too: the subjects, location, layout and record group types and design factors by name,
as validation can't find them by name once they are retired.

Once the migration is validated, retire_breedcafs_ontology deprecates the entries the migration created
and commits a version, which removes them (README §2.5): the current ontology starts anew, and the migrated data
still cites them.
"""
import csv
import json
from dataclasses import dataclass, field

from breedgraph.service_layer.application.ontology_seed import COUNTRY
from breedgraph.adapters.neo4j import Neo4jUnitOfWorkFactory
from breedgraph.domain.model.ontology import (
    OntologyEntryLabel, VersionChange, AxisType, ScaleType, ObservationMethodType, ControlMethodType,
    SubjectInput, LocationTypeInput, LayoutTypeInput, TermInput, ScaleInput, ScaleCategory,
    ObservationMethodInput, ControlMethodInput, TraitInput, ConditionInput, VariableInput, FactorInput,
    RecordGroupTypeInput, RecordGroupExtent
)

from breedcafs_migration.setup.config import BREEDCAFS_DATA_DIR

import logging
logger = logging.getLogger(__name__)


# name, description, parent names
SUBJECTS = [
    ("Field", "An area of land used for growing crops", []),
    ("Trees", "A group of trees within a field whose individual trees are not identified, e.g. a block", ["Field"]),
    ("Tree", "An individual tree", ["Field", "Trees"]),
    ("Branch", "A branch of a tree", ["Tree"]),
    ("Leaves", "A collection of leaves", ["Tree", "Branch"]),
    ("Leaf", "An individual leaf", ["Tree", "Branch", "Leaves"]),
    ("Cherries", "A collection of coffee cherries", ["Tree", "Branch"]),
    ("Cherry", "An individual coffee cherry", ["Tree", "Branch", "Cherries"]),
    ("Green Beans", "Processed green coffee beans", ["Tree"]),
]

# name, description, parent names; Country is expected to exist already
LOCATION_TYPES = [
    ("Region", "A large area of land", ["Country"]),
    ("Farm", "A place where crops are grown", ["Region"]),
    ("Field", "A piece of land used for growing crops", ["Farm"]),
    ("Research Center", "A research institute or laboratory, e.g. where samples were analysed", ["Country"]),
]

# name, description, and the extent of the migration's groupings of the type, which is also its default
RECORD_GROUP_TYPES = [
    (
        "Replicate", "Repeated observations of the same unit at the same time, distinguished by a replicate code",
        RecordGroupExtent.WITHIN_UNIT
    ),
    # Branches are not units: their records are on the tree they were taken from, with a code of each (README §6.1)
    (
        "Branch", "The branch of a tree (or tree sample) a reading was taken from, as a code distinguishing its branches",
        RecordGroupExtent.WITHIN_UNIT
    ),
    (
        "Stratum", "The canopy stratum (Lower, Middle or Upper) of the tree a reading was taken from, as set by the sampling design",
        RecordGroupExtent.SHARED
    ),
    # Leaves measured once are not units either (README §6.1)
    (
        "Leaf", "The leaf of a tree (or tree sample) a reading was taken from, as a code distinguishing its leaves",
        RecordGroupExtent.WITHIN_UNIT
    ),
    # BreedCAFS blocks are not units: the records of what is in them, or was taken from them, have a code (README §6.4)
    (
        "Block", "The design block of a field a reading was taken in, named as in BreedCAFS (block names recur across fields)",
        RecordGroupExtent.WITHIN_GRAPH
    ),
]

RECORD_GROUP_EXTENTS = {name: extent for name, _, extent in RECORD_GROUP_TYPES}

# name, description, axes, parent names
LAYOUT_TYPES = [
    ("Row and Tree", "Trees by row, and position within the row", [AxisType.ORDINAL, AxisType.ORDINAL], []),
]

SCALE_TYPES = {'Date': ScaleType.DATE}

# Factors of the migration's design, recorded on units rather than from BreedCAFS inputs,
# given as curated input rows with the subject they describe.
# Blocks named after a treatment are not migrated as units; their trees get a record of the treatment (README §6.4).
# The block names are the categories.
TREATMENT_FACTORS = [
    {
        'Factor': "Shade Treatment",
        'description': "Shade treatment of trees in the shade trial at La Hilda (Costa Rica), from the block they are in",
        'Condition': "Light Availability",
        'ControlMethod': "Shade cloth", 'ControlMethodType': "ENVIRONMENTAL", 'ControlMethodDescription': "",
        'Scale': "Shade treatment", 'Scale Description': "", 'ScaleType': "NOMINAL",
        'categories': "Full Sun / Shade",
        'subject': "Tree",
    },
    {
        'Factor': "Shade Level Treatment",
        'description': "Shade treatment of trees in the greenhouse in Copenhagen (Denmark), from the block they are in",
        'Condition': "Light Availability",
        'ControlMethod': "Shade cloth", 'ControlMethodType': "ENVIRONMENTAL", 'ControlMethodDescription': "",
        'Scale': "Shade level treatment", 'Scale Description': "", 'ScaleType': "NOMINAL",
        'categories': "Shade Level 1 / Shade Level 2 / Shade Level 3 / Shade Level 4 / Shade Level 5 / 2 Years Low Light Acclimation",
        'subject': "Tree",
    },
]
DESIGN_FACTORS = TREATMENT_FACTORS


@dataclass
class OntologyIds:
    subjects: dict[str, int] = field(default_factory=dict)
    location_types: dict[str, int] = field(default_factory=dict)
    layout_types: dict[str, int] = field(default_factory=dict)
    record_group_types: dict[str, int] = field(default_factory=dict)
    # (BreedCAFS input name, apparatus or '') -> (label, id) of the variable or factor
    inputs: dict[tuple[str, str], tuple[OntologyEntryLabel, int]] = field(default_factory=dict)
    # Factor name -> id, for DESIGN_FACTORS
    design_factors: dict[str, int] = field(default_factory=dict)
    created: int = 0


def clean(value: str) -> str:
    """Values in the exported CSV are wrapped in extra quotes"""
    return (value or '').strip().strip('"').strip()


def parse_list(value: str) -> list[str]:
    """JSON lists, some written with typographic quotes"""
    value = (value or '').replace('“', '"').replace('”', '"').strip()
    return [v.strip() for v in json.loads(value)] if value and value != 'null' else []


def parse_categories(value: str) -> list[str]:
    value = clean(value)
    return [c.strip() for c in value.split('/')] if value and value != 'null' else []


def read_input_subjects() -> dict[str, list[str]]:
    subjects = {}
    with open(BREEDCAFS_DATA_DIR / 'input_subjects.csv') as f:
        for row in csv.DictReader(f):
            subjects.setdefault(row['input'], []).append(row['subject'])
    return subjects


class OntologyPreparation:
    def __init__(self, ontology, ids: OntologyIds):
        self.ontology = ontology
        self.ids = ids

    async def get_or_create(self, label: OntologyEntryLabel, name: str, create) -> tuple[int, bool]:
        entry = await self.ontology.get_entry(name=name, label=label)
        if entry is not None:
            return entry.id, False
        entry = await create()
        self.ids.created += 1
        logger.debug(f"Created {label} {entry.id}")
        return entry.id, True

    async def subjects(self):
        for name, description, parents in SUBJECTS:
            self.ids.subjects[name], _ = await self.get_or_create(
                OntologyEntryLabel.SUBJECT, name,
                lambda: self.ontology.create_subject(
                    SubjectInput(name=name, description=description),
                    parents=[self.ids.subjects[p] for p in parents]
                )
            )

    async def location_types(self):
        country = await self.ontology.get_seeded_entry(COUNTRY)
        if country is None:
            raise ValueError("Country location type not found: it is seeded by setup_initial_data.py")
        self.ids.location_types["Country"] = country.id
        for name, description, parents in LOCATION_TYPES:
            self.ids.location_types[name], _ = await self.get_or_create(
                OntologyEntryLabel.LOCATION_TYPE, name,
                lambda: self.ontology.create_entry(
                    LocationTypeInput(name=name, description=description),
                    parents=[self.ids.location_types[p] for p in parents]
                )
            )

    async def layout_types(self):
        for name, description, axes, parents in LAYOUT_TYPES:
            self.ids.layout_types[name], _ = await self.get_or_create(
                OntologyEntryLabel.LAYOUT_TYPE, name,
                lambda: self.ontology.create_entry(
                    LayoutTypeInput(name=name, description=description, axes=axes),
                    parents=[self.ids.layout_types[p] for p in parents]
                )
            )

    async def record_group_types(self):
        for name, description, extent in RECORD_GROUP_TYPES:
            # an existing type is reused whatever its default extent, as the groupings set their own (programs.py)
            self.ids.record_group_types[name], _ = await self.get_or_create(
                OntologyEntryLabel.RECORD_GROUP_TYPE, name,
                lambda: self.ontology.create_entry(RecordGroupTypeInput(name=name, description=description, default_extent=extent))
            )

    async def scale(self, row: dict) -> int:
        name = row['Scale']
        categories = parse_categories(row['categories'])
        scale_type = row['ScaleType']
        if not scale_type and categories:
            # Only the defoliation classes are categorical without a scale type, and they are ordered
            scale_type = ScaleType.ORDINAL
        scale_type = SCALE_TYPES.get(scale_type) or ScaleType(scale_type)

        async def create():
            return await self.ontology.create_scale(ScaleInput(
                name=name,
                description=row['Scale Description'] or None,
                scale_type=scale_type,
                categories=[ScaleCategory(category) for category in categories]
            ))

        existing = await self.ontology.get_entry(name=name, label=OntologyEntryLabel.SCALE)
        if existing is not None and existing.scale_type is not scale_type:
            raise ValueError(f"The scale {name} is {existing.scale_type.value}, not {scale_type.value}: give the scales distinct names")
        scale_id, _ = await self.get_or_create(OntologyEntryLabel.SCALE, name, create)
        return scale_id

    async def term_ids(self, row: dict) -> list[int]:
        ids = []
        for name in parse_list(row['terms']):
            term_id, _ = await self.get_or_create(
                OntologyEntryLabel.TERM, name,
                lambda: self.ontology.create_entry(TermInput(name=name))
            )
            ids.append(term_id)
        return ids

    async def link_terms(self, entry_id: int, label: OntologyEntryLabel, term_ids: list[int]):
        for term_id in term_ids:
            await self.ontology.link_to_term(source_id=entry_id, source_label=label, term_id=term_id)

    async def variable(self, input_name: str, row: dict, subject_ids: list[int]) -> int:
        trait_id, _ = await self.get_or_create(
            OntologyEntryLabel.TRAIT, row['Trait'],
            lambda: self.ontology.create_trait(
                TraitInput(name=row['Trait'], description=row['Trait Description'] or None),
                subjects=subject_ids
            )
        )
        method_id, _ = await self.get_or_create(
            OntologyEntryLabel.OBSERVATION_METHOD, row['ObservationMethod'],
            lambda: self.ontology.create_entry(ObservationMethodInput(
                name=row['ObservationMethod'],
                description=row['ObservationMethodDescription'] or None,
                observation_type=ObservationMethodType(row['ObservationMethodType'])
            ))
        )
        scale_id = await self.scale(row)
        term_ids = await self.term_ids(row)

        async def create():
            variable = await self.ontology.create_variable(
                VariableInput(name=row['Variable'], description=clean(row['description']) or None, synonyms=self.synonyms(input_name, row['Variable'])),
                trait_id=trait_id, observation_method_id=method_id, scale_id=scale_id
            )
            await self.link_terms(variable.id, OntologyEntryLabel.VARIABLE, term_ids)
            return variable

        variable_id, _ = await self.get_or_create(OntologyEntryLabel.VARIABLE, row['Variable'], create)
        return variable_id

    async def factor(self, input_name: str, row: dict, subject_ids: list[int]) -> int:
        condition_id, _ = await self.get_or_create(
            OntologyEntryLabel.CONDITION, row['Condition'],
            lambda: self.ontology.create_condition(ConditionInput(name=row['Condition']), subjects=subject_ids)
        )
        method_id, _ = await self.get_or_create(
            OntologyEntryLabel.CONTROL_METHOD, row['ControlMethod'],
            lambda: self.ontology.create_entry(ControlMethodInput(
                name=row['ControlMethod'],
                description=row['ControlMethodDescription'] or None,
                control_type=ControlMethodType(row['ControlMethodType'])
            ))
        )
        scale_id = await self.scale(row)
        term_ids = await self.term_ids(row)

        async def create():
            factor = await self.ontology.create_factor(
                FactorInput(name=row['Factor'], description=clean(row['description']) or None, synonyms=self.synonyms(input_name, row['Factor'])),
                condition_id=condition_id, control_method_id=method_id, scale_id=scale_id
            )
            await self.link_terms(factor.id, OntologyEntryLabel.FACTOR, term_ids)
            return factor

        factor_id, _ = await self.get_or_create(OntologyEntryLabel.FACTOR, row['Factor'], create)
        return factor_id

    @staticmethod
    def synonyms(input_name: str, name: str) -> list[str]:
        """Keep the BreedCAFS input name, for anyone looking for it"""
        return [input_name] if input_name.casefold() != name.casefold() else []

    async def inputs(self) -> list[str]:
        """Returns the inputs that are not curated enough to map to a variable or factor"""
        input_subjects = read_input_subjects()
        incomplete = []
        with open(BREEDCAFS_DATA_DIR / 'input_details_curated.csv', encoding='utf-8-sig') as f:
            for row in csv.DictReader(f):
                row = {k: v.strip() for k, v in row.items()}
                input_name = clean(row['name'])
                key = (input_name, row.get('Apparatus', ''))
                subject_ids = [self.ids.subjects[s] for s in input_subjects.get(input_name, [])]
                if row['Variable'] and row['Trait'] and row['ObservationMethod'] and row['Scale']:
                    variable_id = await self.variable(input_name, row, subject_ids)
                    self.ids.inputs[key] = (OntologyEntryLabel.VARIABLE, variable_id)
                elif row['Factor'] and row['Condition'] and row['ControlMethod'] and row['Scale']:
                    factor_id = await self.factor(input_name, row, subject_ids)
                    self.ids.inputs[key] = (OntologyEntryLabel.FACTOR, factor_id)
                else:
                    incomplete.append(input_name)
        return incomplete


async def design_factors(preparation: 'OntologyPreparation') -> None:
    for row in DESIGN_FACTORS:
        row = {**row, 'terms': ''}
        preparation.ids.design_factors[row['Factor']] = await preparation.factor(
            row['Factor'], row, subject_ids=[preparation.ids.subjects[row['subject']]]
        )


def write_input_mapping(ids: OntologyIds) -> None:
    with open(BREEDCAFS_DATA_DIR / 'ontology_ids.csv', 'w', newline='') as f:
        writer = csv.writer(f)
        writer.writerow(['input', 'apparatus', 'label', 'id'])
        for (input_name, apparatus), (label, entry_id) in sorted(ids.inputs.items()):
            writer.writerow([input_name, apparatus, label.value, entry_id])


def write_entry_mapping(ids: OntologyIds) -> None:
    with open(BREEDCAFS_DATA_DIR / 'ontology_entry_ids.csv', 'w', newline='') as f:
        writer = csv.writer(f)
        writer.writerow(['label', 'name', 'id'])
        for label, entries in (
                (OntologyEntryLabel.SUBJECT, ids.subjects),
                (OntologyEntryLabel.LOCATION_TYPE, ids.location_types),
                (OntologyEntryLabel.LAYOUT_TYPE, ids.layout_types),
                (OntologyEntryLabel.RECORD_GROUP_TYPE, ids.record_group_types),
                (OntologyEntryLabel.FACTOR, ids.design_factors)
        ):
            for name, entry_id in entries.items():
                writer.writerow([label.value, name, entry_id])


async def prepare_breedcafs_ontology(uow_factory: Neo4jUnitOfWorkFactory, user_id: int, commit_version: bool = True) -> OntologyIds:
    ids = OntologyIds()
    async with uow_factory.get_uow(user_id=user_id) as uow:
        preparation = OntologyPreparation(uow.ontology, ids)
        await preparation.subjects()
        await preparation.location_types()
        await preparation.layout_types()
        await preparation.record_group_types()
        incomplete = await preparation.inputs()
        await design_factors(preparation)
        if incomplete:
            logger.warning(f"Inputs not mapped, as their curation is incomplete: {incomplete}")
        if ids.created and commit_version:
            await uow.ontology.commit_version(
                version_change=VersionChange.MINOR,
                comment="Entries for data migrated from BreedCAFS"
            )
        await uow.commit()
    logger.info(f"Prepared the ontology: {ids.created} entries created, {len(ids.inputs)} inputs mapped")
    write_input_mapping(ids)
    write_entry_mapping(ids)
    return ids


# The entries the migration user created that the current version still has: an entry's first patch is its creation
CREATED_ENTRIES = """
    MATCH (entry:OntologyEntry)-[:HAS_LIFECYCLE]->(lifecycle:OntologyLifecycle)
    WHERE lifecycle.removed IS NULL
    MATCH (entry)<-[for_entry:FOR_ENTRY]-(patch:OntologyEntryPatch)
    WITH entry, patch ORDER BY for_entry.time
    WITH entry, head(collect(patch)) AS creation
    MATCH (:User {id: $user_id})-[:CONTRIBUTED]->(:UserOntologyContributions)-[:CONTRIBUTED]->(creation)
    RETURN entry.id AS id ORDER BY id
"""

RETIREMENT_COMMENT = "Retire the entries created for the data migrated from BreedCAFS"


async def retire_breedcafs_ontology(uow_factory: Neo4jUnitOfWorkFactory, user_id: int) -> int:
    """
    Deprecates the entries the migration created, and commits a major version, which removes them.
    Entries it found already there (e.g. Country) are kept. Returns the number retired: running it again retires none.
    """
    async with uow_factory.get_uow(user_id=user_id) as uow:
        result = await uow.tx.run(CREATED_ENTRIES, user_id=user_id)
        entry_ids = [record['id'] async for record in result]
        if not entry_ids:
            logger.info("No entries to retire: the migration's entries are already removed")
            return 0
        await uow.ontology.deprecate_entries(entry_ids)
        commit = await uow.ontology.commit_version(version_change=VersionChange.MAJOR, comment=RETIREMENT_COMMENT)
        await uow.commit()
    logger.info(f"Retired {len(entry_ids)} entries the migration created: removed at version {commit.version}")
    return len(entry_ids)
