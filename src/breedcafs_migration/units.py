"""
Units for the BreedCAFS items (README.md §6, 1_4_Extract_Units.md).

Each BreedCAFS field is a block, rooted at a Field unit positioned at the field's location.
Every other item is a unit in its field's block, `PRIVATE` and controlled by the migration team, with:
  - its subject, from item_name_subject_sources_sinks.csv: the item type, or the sample unit for samples,
    with BreedCAFS blocks as `Trees` (README §6.4);
  - its parents, the items it is in or was taken from, or else its field;
  - its germplasm, from item_variety.csv and germplasm_ids.csv, unless it was pooled from parents of different varieties,
    when its parents say what it contains;
  - positions: trees in their layout (unit_positions.csv), and samples at their location (sample_positions.csv).
Items in skipped_items.csv are left out (README §6.5), as are the duplicates in DUPLICATE_ITEMS.
Blocks named after a treatment (TREATMENT_FIELDS) are not units: their trees are placed under the field,
and get a record of the treatment. Branches get a record of their stratum (branch_strata.csv).
These records are written to factor_records.csv, for the datasets phase.

A unit keeps its BreedCAFS name, or its uid where it has none, and is described as "BreedCAFS item <uid>",
by which running this again finds the units created before.
Writes unit_ids.csv, mapping each BreedCAFS item to its unit.
"""
import csv
import json
from dataclasses import dataclass, field
from datetime import date

from numpy import datetime64

from breedgraph.adapters.neo4j import Neo4jUnitOfWorkFactory
from breedgraph.domain.model.blocks import Block, UnitInput, Position

from breedcafs_migration.bootstrap import MigrationContext
from breedcafs_migration.layouts import LayoutIds, tree_group, ROW_AND_TREE
from breedcafs_migration.locations import LocationIds
from breedcafs_migration.ontology import TREATMENT_FACTORS, STRATUM_FACTOR
from breedcafs_migration.setup.config import BREEDCAFS_DATA_DIR

import logging
logger = logging.getLogger(__name__)

# BreedCAFS item type or sample unit -> subject name in the ontology
SUBJECTS = {
    "Field": "Field",
    "Block": "Trees",
    "Tree": "Tree",
    "Branch": "Branch",
    "Leaf": "Leaf",
    "Leaves": "Leaves",
    "Cherry": "Cherry",
    "Cherries": "Cherries",
    "Green Beans": "Green Beans",
}

# Trees registered twice, with the same name, variety, block, position and records, and no samples:
# the second of each pair is left out, with its records (README §6.5)
DUPLICATE_ITEMS = {
    "24_T1080": "24_T1079",
    "24_T1090": "24_T1089",
    "24_T1100": "24_T1099",
}

# Fields whose blocks are named after a treatment -> the factor whose categories they are (README §6.4)
TREATMENT_FIELDS = {
    "25": "Shade Treatment",
    "26": "Shade Treatment",
    "27": "Shade Treatment",
    "35": "Shade Level Treatment",
}


@dataclass
class Item:
    uid: str
    field_uid: str
    name: str | None
    subject: str
    parents: list[str]  # uids of the items it is in or was taken from, within its field


@dataclass
class UnitIds:
    # BreedCAFS item uid -> unit id
    units: dict[str, int] = field(default_factory=dict)
    # (item uid, factor name, category): treatments of trees in blocks named after a treatment, and strata of branches
    factor_records: list[tuple[str, str, str]] = field(default_factory=list)
    created: int = 0


def clean(value: str) -> str:
    """Values in the exported CSVs are wrapped in extra quotes"""
    value = (value or '').strip().strip('"').strip()
    return '' if value == 'null' else value


def read_csv(name: str) -> list[dict[str, str]]:
    with open(BREEDCAFS_DATA_DIR / name, encoding='utf-8-sig') as f:
        return list(csv.DictReader(f))


def description(uid: str) -> str:
    return f"BreedCAFS item {uid}"


def coordinate(value: str) -> str:
    """Coordinates are stored as strings, as the API gives them; rows and trees are whole numbers, e.g. 4.0 as '4'"""
    return str(int(float(value)))


def read_items() -> dict[str, Item]:
    skipped = {row['item_uid'] for row in read_csv('skipped_items.csv')} | set(DUPLICATE_ITEMS)
    items = {}
    for row in read_csv('item_name_subject_sources_sinks.csv'):
        uid = clean(row['item_uid'])
        if uid in skipped:
            continue
        sources = json.loads(row['source_items'])
        items[uid] = Item(
            uid=uid,
            field_uid=uid.split('_')[0],
            name=clean(row['name']) or None,
            subject=clean(row['subject']),
            # Items directly in a field list the field's uid as an integer
            parents=[source for source in sources if isinstance(source, str) and source not in skipped]
        )
    return items


class UnitPlan:
    """What to create for each item, from the extracted files"""

    def __init__(self, items: dict[str, Item]):
        self.items = items
        self.treatment_blocks = {
            uid: (TREATMENT_FIELDS[item.field_uid], item.name)
            for uid, item in items.items()
            if item.subject == "Block" and item.field_uid in TREATMENT_FIELDS
        }
        categories = {row['Factor']: [c.strip() for c in row['categories'].split('/')] for row in TREATMENT_FACTORS}
        unknown = [(factor, name) for factor, name in self.treatment_blocks.values() if name not in categories[factor]]
        if unknown:
            raise ValueError(f"Blocks whose names are not categories of their treatment factor: {unknown}")
        unmapped = sorted({item.subject for item in items.values()} - set(SUBJECTS))
        if unmapped:
            raise ValueError(f"No subject is given for these item types or sample units: {unmapped}")

        self.varieties = {clean(row['item_uid']): clean(row['variety']) for row in read_csv('item_variety.csv')}
        self.tree_positions: dict[str, tuple[str, str, str]] = {}  # uid -> (group, row, tree)
        for row in read_csv('unit_positions.csv'):
            uid = clean(row['item_uid'])
            if uid in items:
                group = tree_group(clean(row['field_uid']), clean(row['layout_level']), clean(row['layout_name']), items[uid].name or '')
                self.tree_positions[uid] = (group, coordinate(row['row']), coordinate(row['column']))
        self.strata = {clean(row['item_uid']): json.loads(row['strata'])[0] for row in read_csv('branch_strata.csv')}
        self.sample_positions = {
            clean(row['item_uid']): (clean(row['location']), clean(row['date'])) for row in read_csv('sample_positions.csv')
        }

    def lineage_varieties(self, uid: str) -> set[str]:
        """The variety of an item, or else the varieties of its parents"""
        if uid in self.varieties:
            return {self.varieties[uid]}
        item = self.items.get(uid)
        if item is None or uid == item.field_uid:
            return set()
        return set().union(*(self.lineage_varieties(parent) for parent in self.parents(item)))

    def germplasm_variety(self, item: Item) -> str | None:
        """The item's variety, unless it was pooled from parents of different varieties"""
        parents = self.parents(item)
        if len(parents) > 1 and len(set().union(*(self.lineage_varieties(parent) for parent in parents))) > 1:
            return None
        return self.varieties.get(item.uid)

    def mixed_pools(self) -> list[str]:
        """Items pooled from parents of different varieties, whose germplasm is left unset"""
        return sorted(uid for uid, item in self.items.items() if uid in self.varieties and self.germplasm_variety(item) is None)

    def parents(self, item: Item) -> list[str]:
        """Parent uids: blocks named after a treatment are replaced by the field, as is no parent at all"""
        parents = []
        for parent in item.parents:
            parent = item.field_uid if parent in self.treatment_blocks else parent
            if parent not in parents:
                parents.append(parent)
        return parents or [item.field_uid]

    def ordered(self, field_uid: str) -> list[Item]:
        """The items of a field to create as units, parents before children, without the field itself"""
        items = [
            item for item in self.items.values()
            if item.field_uid == field_uid and item.uid != field_uid and item.uid not in self.treatment_blocks
        ]
        depths: dict[str, int] = {field_uid: 0}

        def depth(uid: str) -> int:
            if uid not in depths:
                depths[uid] = 1 + max(depth(parent) for parent in self.parents(self.items[uid]))
            return depths[uid]

        return sorted(items, key=lambda item: (depth(item.uid), item.uid))

    def factor_records(self) -> list[tuple[str, str, str]]:
        treatments = [
            (item.uid, *self.treatment_blocks[parent])
            for item in self.items.values()
            for parent in item.parents if parent in self.treatment_blocks
        ]
        strata = [(uid, STRATUM_FACTOR['Factor'], stratum) for uid, stratum in self.strata.items() if uid in self.items]
        return sorted(treatments + strata)

    def positions(self, item: Item, field_location: int, layouts: LayoutIds, sample_locations: dict[str, int]) -> list[Position]:
        positions = []
        if item.subject == "Field":
            positions.append(Position(location_id=field_location))
        if item.uid in self.tree_positions:
            group, row, tree = self.tree_positions[item.uid]
            positions.append(Position(
                location_id=field_location,
                layout_id=layouts.layouts[(item.field_uid, group, ROW_AND_TREE)],
                coordinates=[row, tree]
            ))
        if item.uid in self.sample_positions:
            location, start = self.sample_positions[item.uid]
            positions.append(Position(location_id=sample_locations[location], start=datetime64(date.fromisoformat(start))))
        return positions


def unit_input(plan: UnitPlan, item: Item, subjects: dict[str, int], germplasm: dict[str, int], positions: list[Position]) -> UnitInput:
    variety = plan.germplasm_variety(item)
    return UnitInput(
        subject=subjects[SUBJECTS[item.subject]],
        germplasm=germplasm[variety] if variety else None,
        name=item.name or item.uid,
        description=description(item.uid),
        positions=positions
    )


def units_by_description(block: Block) -> dict[str, int]:
    return {unit.description: unit_id for unit_id, unit in block.entries.items() if unit.description}


async def prepare_breedcafs_units(
        uow_factory: Neo4jUnitOfWorkFactory,
        context: MigrationContext,
        subjects: dict[str, int],
        germplasm: dict[str, int],
        locations: LocationIds,
        layouts: LayoutIds
) -> UnitIds:
    ids = UnitIds()
    plan = UnitPlan(read_items())
    ids.factor_records = plan.factor_records()
    if plan.mixed_pools():
        logger.warning(f"Pooled from parents of different varieties, so no germplasm is set: {plan.mixed_pools()}")
    field_uids = sorted({item.field_uid for item in plan.items.values()}, key=int)

    for field_uid in field_uids:
        field_location = locations.fields[field_uid]
        root = plan.items[field_uid]
        async with uow_factory.get_uow(user_id=context.user_id, write_team=context.team_id) as uow:
            blocks = uow.repositories.blocks
            block = None
            async for found in blocks.get_all(location_ids=[field_location]):
                if found.root.description == description(field_uid):
                    block = found
                    break
            if block is None:
                block = await blocks.create(unit_input(
                    plan, root, subjects, germplasm, plan.positions(root, field_location, layouts, locations.sample_locations)
                ))
                ids.created += 1
            existing = units_by_description(block)
            unit_ids = {field_uid: existing[description(field_uid)]}
            for item in plan.ordered(field_uid):
                if description(item.uid) in existing:
                    unit_ids[item.uid] = existing[description(item.uid)]
                    continue
                positions = plan.positions(item, field_location, layouts, locations.sample_locations)
                unit_ids[item.uid] = block.add_unit(
                    unit_input(plan, item, subjects, germplasm, positions),
                    parents=[unit_ids[parent] for parent in plan.parents(item)]
                )
                ids.created += 1
            await uow.commit()
            root_id = block.get_root_id()

        # Read again for the ids of units created above
        async with uow_factory.get_uow(user_id=context.user_id) as uow:
            block = await uow.repositories.blocks.get(unit_id=root_id)
            stored = units_by_description(block)
            for uid in [field_uid, *(item.uid for item in plan.ordered(field_uid))]:
                ids.units[uid] = stored[description(uid)]
        logger.info(f"Field {field_uid}: {len(ids.units)} units so far, {ids.created} created")

    write_mappings(ids)
    return ids


def write_mappings(ids: UnitIds) -> None:
    with open(BREEDCAFS_DATA_DIR / 'unit_ids.csv', 'w', newline='') as f:
        writer = csv.writer(f)
        writer.writerow(['item_uid', 'unit_id'])
        for uid, unit_id in ids.units.items():
            writer.writerow([uid, unit_id])
    with open(BREEDCAFS_DATA_DIR / 'factor_records.csv', 'w', newline='') as f:
        writer = csv.writer(f)
        writer.writerow(['item_uid', 'factor', 'category'])
        writer.writerows(ids.factor_records)
