"""
Layouts of the BreedCAFS fields (README.md §4, 1_2_Extract_Layouts.md).

From field_layout_types.csv, each field has, at its location:
  - where trees have row and column positions, a "Row and Tree" layout,
    or one per block where rows and trees are numbered per block (field 29),
    and one for each separate planting in the field with its own rows (PLANTINGS);
Each layout is the root of its own layout tree. Branch strata are record group codes, not positions (units.py).
Layouts are matched by name and type at the field's location, or created, `PRIVATE` and controlled by the migration team.

Running this again matches the layouts created before.
Writes layout_ids.csv, mapping each field (and block or planting) and BreedCAFS layout type to its layout.
The units phase finds a tree's layout with tree_group.
"""
import csv
import re
from dataclasses import dataclass, field

from breedgraph.adapters.neo4j import Neo4jUnitOfWorkFactory
from breedgraph.domain.model.layout_trees import LayoutInput

from breedcafs_migration.bootstrap import MigrationContext
from breedcafs_migration.locations import read_fields
from breedcafs_migration.setup.config import BREEDCAFS_DATA_DIR

import logging
logger = logging.getLogger(__name__)

# Layout type name -> axis names, in the order of the layout type's axes
AXES = {
    "Row and Tree": ["Row", "Tree"],
}

# The layout type named in unit_positions.csv
ROW_AND_TREE = "row_and_tree"

# Separate plantings within a field, with their own rows and trees, recognised by tree name.
# In field 5 (ED5), the trees named with a code citing another field, e.g. "7-ED6-1D2", were planted in July 2018,
# in rows and columns of their own; many share a position, to be resolved with the partner (README §4).
PLANTINGS = {
    "5": [("July 2018 planting", re.compile(r'^7-ED\d+-'))],
}

# (field uid, block or planting name or '', BreedCAFS layout type)
LayoutKey = tuple[str, str, str]


@dataclass
class LayoutIds:
    layouts: dict[LayoutKey, int] = field(default_factory=dict)
    created: int = 0


def clean(value: str) -> str:
    """Values in the exported CSVs are wrapped in extra quotes"""
    return (value or '').strip().strip('"').strip()


def read_csv(name: str) -> list[dict[str, str]]:
    with open(BREEDCAFS_DATA_DIR / name, encoding='utf-8-sig') as f:
        return [{key: clean(value) for key, value in row.items()} for row in csv.DictReader(f)]


def tree_group(field_uid: str, layout_level: str, layout_name: str, tree_name: str) -> str:
    """The block or planting whose layout a tree's position in unit_positions.csv is in, or '' for the field's layout"""
    if layout_level == 'block':
        return layout_name
    for planting, pattern in PLANTINGS.get(field_uid, []):
        if pattern.match(tree_name):
            return planting
    return ''


def planned_layouts() -> dict[LayoutKey, tuple[str, str]]:
    """Each layout to create: its key, and its name and layout type name"""
    fields = {row['field_uid']: row['field'] for row in read_fields(BREEDCAFS_DATA_DIR)}
    # Blocks with their own rows and trees, from the positions of their trees
    blocks: dict[str, set[str]] = {}
    for row in read_csv('unit_positions.csv'):
        if row['layout_level'] == 'block':
            blocks.setdefault(row['field_uid'], set()).add(row['layout_name'])

    layouts = {}
    for row in read_csv('field_layout_types.csv'):
        field_uid = row['f.uid']
        field_name = fields[field_uid]
        if row['row_and_tree'] == 'true':
            type_name = "Row and Tree"
            if row['row_and_tree_per_block'] == 'true':
                for block in sorted(blocks.get(field_uid, ())):
                    layouts[(field_uid, block, ROW_AND_TREE)] = (f"{field_name} {block}: {type_name}", type_name)
            else:
                layouts[(field_uid, '', ROW_AND_TREE)] = (f"{field_name}: {type_name}", type_name)
            for planting, _ in PLANTINGS.get(field_uid, []):
                layouts[(field_uid, planting, ROW_AND_TREE)] = (f"{field_name} {planting}: {type_name}", type_name)
    return layouts


async def prepare_breedcafs_layouts(
        uow_factory: Neo4jUnitOfWorkFactory,
        context: MigrationContext,
        layout_types: dict[str, int],
        field_locations: dict[str, int]
) -> LayoutIds:
    ids = LayoutIds()
    planned = planned_layouts()
    async with uow_factory.get_uow(user_id=context.user_id, write_team=context.team_id) as uow:
        layout_trees = uow.repositories.layout_trees
        for key, (name, type_name) in planned.items():
            location_id = field_locations[key[0]]
            type_id = layout_types[type_name]
            existing = [
                layout_tree.root async for layout_tree in layout_trees.get_all(location_id=location_id)
                if layout_tree.root.type == type_id and layout_tree.root.name == name
            ]
            if existing:
                ids.layouts[key] = existing[0].id
                continue
            layout_tree = await layout_trees.create(
                LayoutInput(name=name, type=type_id, location=location_id, axes=AXES[type_name])
            )
            ids.layouts[key] = layout_tree.get_root_id()
            ids.created += 1
        await uow.commit()

    logger.info(f"Prepared layouts: {ids.created} of {len(ids.layouts)} created")
    write_layout_mapping(ids)
    return ids


def write_layout_mapping(ids: LayoutIds) -> None:
    with open(BREEDCAFS_DATA_DIR / 'layout_ids.csv', 'w', newline='') as f:
        writer = csv.writer(f)
        writer.writerow(['field_uid', 'group', 'layout_type', 'layout_id'])
        for (field_uid, group, layout_type), layout_id in sorted(ids.layouts.items(), key=lambda item: (int(item[0][0]), item[0][1:])):
            writer.writerow([field_uid, group, layout_type, layout_id])
