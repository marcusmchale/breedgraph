"""
Germplasm for the BreedCAFS varieties referenced by items (README.md §5, 1_3_Extract_Germplasm.md).

Each variety in varieties.csv is matched, by its normalised name or a synonym, to a germplasm entry the migration user can read.
A name already used by an entry the migration user cannot read is reported, rather than created again.
Varieties without a match are created, controlled by the migration team:
  - crosses, named "maternal x paternal", with MATERNAL and PATERNAL source relationships from their parents;
  - grafts, named "scion / rootstock", with TISSUE source relationships from the scion and the rootstock,
    described as "Scion" and "Rootstock";
  - and other varieties with the "BreedCAFS Varieties" entry as their source, to be curated later with the partners.
Parents and graft parts are matched ignoring case and spaces, as some are written without the space of the variety,
e.g. "ET26A1" for "ET26 A1". Cross parents that do not exist are created as other varieties are.

Running this again matches the entries created before.
Writes germplasm_ids.csv, mapping each variety to its germplasm entry,
with whether it was matched to an existing entry or created from BreedCAFS.
"""
import csv
import re
from dataclasses import dataclass, field

from breedgraph.adapters.neo4j import Neo4jUnitOfWorkFactory
from breedgraph.domain.model.germplasm import GermplasmInput, GermplasmStored, GermplasmRelationship, GermplasmSourceType

from breedcafs_migration.bootstrap import MigrationContext
from breedcafs_migration.setup.config import BREEDCAFS_DATA_DIR

import logging
logger = logging.getLogger(__name__)

BREEDCAFS_VARIETIES = "BreedCAFS Varieties"
BREEDCAFS_VARIETIES_DESCRIPTION = (
    "Varieties referenced in BreedCAFS that did not match an existing germplasm entry when the data was migrated. "
    "Their sources are to be curated."
)
VARIETY_DESCRIPTION = "Variety referenced in BreedCAFS"
PARENT_DESCRIPTION = "Parent of crosses referenced in BreedCAFS"
SCION = "Scion"
ROOTSTOCK = "Rootstock"


class GermplasmNameConflict(Exception):
    """Variety names used by germplasm entries the migration user cannot read"""


@dataclass
class GermplasmIds:
    varieties_id: int | None = None
    # BreedCAFS variety name -> germplasm entry id
    varieties: dict[str, int] = field(default_factory=dict)
    # Variety names created from BreedCAFS: under the BreedCAFS Varieties entry, or as crosses or grafts
    created_from_breedcafs: set[str] = field(default_factory=set)
    # Cross parents that are not BreedCAFS varieties, created under the BreedCAFS Varieties entry
    parents_created: set[str] = field(default_factory=set)
    created: int = 0


def collapse_whitespace(name: str) -> str:
    return re.sub(r'\s+', ' ', name).strip()


def normalise(name: str) -> str:
    return collapse_whitespace(name).casefold()


def compact(name: str) -> str:
    return re.sub(r'\s+', '', name).casefold()


def split_name(name: str, separator: str) -> tuple[str, str] | None:
    parts = [part.strip() for part in re.split(separator, name)]
    return (parts[0], parts[1]) if len(parts) == 2 else None


def cross_parents(name: str) -> tuple[str, str] | None:
    """The maternal and paternal parents of a cross named "maternal x paternal\""""
    return split_name(name, r'\s+[xX]\s+')


def graft_parts(name: str) -> tuple[str, str] | None:
    """The scion and rootstock of a graft named "scion / rootstock\""""
    return split_name(name, r'\s+/\s+')


def read_varieties() -> list[str]:
    with open(BREEDCAFS_DATA_DIR / 'varieties.csv', encoding='utf-8-sig') as f:
        return [row[0].strip().strip('"') for row in csv.reader(f) if row][1:]


class GermplasmPreparation:
    def __init__(self, germplasm, ids: GermplasmIds):
        self.germplasm = germplasm
        self.ids = ids
        self.entries: dict[str, GermplasmStored] = {}  # by normalised name and synonym
        self.compact_entries: dict[str, GermplasmStored] = {}  # by name and synonym, ignoring case and spaces
        self.under_varieties: set[int] = set()  # entries with the BreedCAFS Varieties entry as their source

    def add(self, entry: GermplasmStored) -> None:
        for name in entry.names:
            self.entries.setdefault(normalise(name), entry)
            self.compact_entries.setdefault(compact(name), entry)

    async def read_entries(self) -> None:
        """Entries the user cannot read come back redacted, and are left out"""
        async for entry in self.germplasm.get_entries():
            if entry.name != entry.redacted_str:
                self.add(entry)

    def find(self, name: str) -> GermplasmStored | None:
        return self.entries.get(normalise(name))

    def find_part(self, name: str) -> GermplasmStored | None:
        return self.find(name) or self.compact_entries.get(compact(name))

    async def check_conflicts(self, names: list[str]) -> None:
        conflicts = [
            name for name in names
            if self.find(name) is None and await self.germplasm.persistence.name_in_use(collapse_whitespace(name))
        ]
        if conflicts:
            raise GermplasmNameConflict(
                f"These names are used by germplasm entries the migration user cannot read: {conflicts}. "
                f"Give the migration team read access to them, or release them, and run this again."
            )

    async def varieties_entry(self) -> None:
        entry = self.find(BREEDCAFS_VARIETIES)
        if entry is None:
            entry = await self.germplasm.create_entry(
                GermplasmInput(name=BREEDCAFS_VARIETIES, description=BREEDCAFS_VARIETIES_DESCRIPTION)
            )
            self.ids.created += 1
            self.add(entry)
        self.ids.varieties_id = entry.id
        self.under_varieties = {
            relationship.sink_id
            async for relationship in self.germplasm.get_sink_relationships(entry.id)
            if relationship.source_id == entry.id
        }

    async def variety(self, name: str, description: str = VARIETY_DESCRIPTION) -> GermplasmStored:
        """A matching entry, or a new one with the BreedCAFS Varieties entry as its source"""
        entry = self.find(name)
        if entry is None:
            entry = await self.germplasm.create_entry(GermplasmInput(name=collapse_whitespace(name), description=description))
            await self.germplasm.create_relationship(GermplasmRelationship(
                source_id=self.ids.varieties_id,
                sink_id=entry.id,
                source_type=GermplasmSourceType.UNKNOWN,
                description="Referenced in BreedCAFS; the source is to be curated"
            ))
            self.ids.created += 1
            self.under_varieties.add(entry.id)
            self.add(entry)
        return entry

    async def derived(
            self,
            name: str,
            description: str,
            sources: list[tuple[GermplasmStored, GermplasmSourceType, str | None]]
    ) -> tuple[GermplasmStored, bool]:
        """
        A matching entry, or a new one with the given sources.
        Also returns whether the entry has these sources, i.e. was created from BreedCAFS.
        """
        expected = {(source.id, source_type, source_description) for source, source_type, source_description in sources}
        entry = self.find(name)
        if entry is None:
            entry = await self.germplasm.create_entry(GermplasmInput(name=collapse_whitespace(name), description=description))
            await self.germplasm.create_relationships([
                GermplasmRelationship(source_id=source_id, sink_id=entry.id, source_type=source_type, description=source_description)
                for source_id, source_type, source_description in expected
            ])
            self.ids.created += 1
            self.add(entry)
            return entry, True
        existing = {
            (relationship.source_id, relationship.source_type, relationship.description)
            async for relationship in self.germplasm.get_source_relationships(entry.id)
        }
        return entry, expected <= existing

    async def cross(self, name: str) -> tuple[GermplasmStored, bool]:
        maternal_name, paternal_name = cross_parents(name)
        parents = []
        for parent_name in (maternal_name, paternal_name):
            parent = self.find_part(parent_name)
            if parent is None:
                parent = await self.variety(parent_name, description=PARENT_DESCRIPTION)
                self.ids.parents_created.add(parent_name)
            parents.append(parent)
        return await self.derived(
            name,
            f"Cross of {maternal_name} (maternal) and {paternal_name} (paternal), referenced in BreedCAFS",
            [(parents[0], GermplasmSourceType.MATERNAL, None), (parents[1], GermplasmSourceType.PATERNAL, None)]
        )

    async def graft(self, name: str) -> tuple[GermplasmStored, bool]:
        scion_name, rootstock_name = graft_parts(name)
        parts = []
        for part_name, part in ((scion_name, SCION), (rootstock_name, ROOTSTOCK)):
            entry = self.find_part(part_name)
            if entry is None:
                raise ValueError(f"The {part.lower()} of the graft {name} is not a germplasm entry: {part_name}")
            parts.append((entry, GermplasmSourceType.TISSUE, part))
        return await self.derived(
            name, f"{scion_name} grafted onto {rootstock_name} rootstock, referenced in BreedCAFS", parts
        )

    async def prepare(self, varieties: list[str]) -> None:
        await self.read_entries()
        await self.check_conflicts([BREEDCAFS_VARIETIES, *varieties])
        await self.varieties_entry()

        crosses = [name for name in varieties if cross_parents(name) is not None]
        grafts = [name for name in varieties if graft_parts(name) is not None]
        # Other varieties first, so crosses and grafts find their parts among them
        for name in varieties:
            if name in crosses or name in grafts:
                continue
            entry = await self.variety(name)
            self.record(name, entry, from_breedcafs=entry.id in self.under_varieties)
        for name in crosses:
            self.record(name, *await self.cross(name))
        for name in grafts:
            self.record(name, *await self.graft(name))

    def record(self, name: str, entry: GermplasmStored, from_breedcafs: bool) -> None:
        self.ids.varieties[name] = entry.id
        if from_breedcafs:
            self.ids.created_from_breedcafs.add(name)


async def prepare_breedcafs_germplasm(uow_factory: Neo4jUnitOfWorkFactory, context: MigrationContext) -> GermplasmIds:
    ids = GermplasmIds()
    async with uow_factory.get_uow(user_id=context.user_id, write_team=context.team_id) as uow:
        await GermplasmPreparation(uow.germplasm, ids).prepare(read_varieties())
        await uow.commit()

    logger.info(
        f"Prepared germplasm: {ids.created} entries created, "
        f"{len(ids.varieties) - len(ids.created_from_breedcafs)} of {len(ids.varieties)} varieties matched existing entries"
    )
    if ids.parents_created:
        logger.info(f"Cross parents created under {BREEDCAFS_VARIETIES}: {sorted(ids.parents_created)}")
    write_variety_mapping(ids)
    return ids


def write_variety_mapping(ids: GermplasmIds) -> None:
    with open(BREEDCAFS_DATA_DIR / 'germplasm_ids.csv', 'w', newline='') as f:
        writer = csv.writer(f)
        writer.writerow(['variety', 'germplasm_id', 'source'])
        for name, entry_id in sorted(ids.varieties.items()):
            writer.writerow([name, entry_id, 'breedcafs' if name in ids.created_from_breedcafs else 'existing'])
