import csv
import shutil

import pytest
import pytest_asyncio

from breedgraph.domain.model.accounts import OntologyRole
from breedgraph.domain.model.controls import ReadRelease
from breedgraph.domain.model.ontology import LayoutTypeInput, LocationTypeInput, OntologyEntryLabel, AxisType
from breedgraph.domain.model.regions import LocationInput

from breedcafs_migration import layouts
from breedcafs_migration.bootstrap import MigrationContext
from breedcafs_migration.layouts import prepare_breedcafs_layouts, planned_layouts, tree_group, ROW_AND_TREE
from breedcafs_migration.setup.config import BREEDCAFS_DATA_DIR

from tests.breedgraph.scenarios.account_builder import AccountBuilder

# As exported: values wrapped in extra quotes
FIELDS = [
    {'field_uid': uid, 'field': f'"""{name}"""', 'farm': '"""Farm"""', 'region': '"""Region"""', 'country': '"""Nicaragua"""'}
    for uid, name in (('1', 'ED1'), ('5', 'ED5'), ('18', 'Max Padilla'), ('29', 'La Cumplida'), ('40', 'Lab Field'))
]
LAYOUT_TYPES = [
    {'f.uid': '1', 'row_and_tree': 'true', 'row_and_tree_per_block': 'false', 'row_tree_and_stratum': 'true'},
    {'f.uid': '5', 'row_and_tree': 'true', 'row_and_tree_per_block': 'false', 'row_tree_and_stratum': 'true'},
    {'f.uid': '18', 'row_and_tree': 'true', 'row_and_tree_per_block': 'false', 'row_tree_and_stratum': 'true'},
    {'f.uid': '29', 'row_and_tree': 'true', 'row_and_tree_per_block': 'true', 'row_tree_and_stratum': 'false'},
    {'f.uid': '40', 'row_and_tree': 'false', 'row_and_tree_per_block': 'false', 'row_tree_and_stratum': 'false'},
]
POSITIONS = [
    {'field_uid': '29', 'item_uid': f'"""29_T{i}"""', 'layout_type': '"""row_and_tree"""', 'layout_level': '"""block"""',
     'layout_name': f'"""{block}"""', 'row': '1.0', 'column': f'{i}.0', 'stratum': 'null'}
    for i, block in enumerate(['Block A', 'Block B', 'Block A'])
] + [
    {'field_uid': field_uid, 'item_uid': f'"""{field_uid}_T1"""', 'layout_type': '"""row_and_tree"""', 'layout_level': '"""field"""',
     'layout_name': f'"""ED{field_uid}"""', 'row': '1.0', 'column': '1.0', 'stratum': 'null'}
    for field_uid in ('1', '5', '18')
]



def write_csv(path, rows):
    with open(path, 'w', newline='', encoding='utf-8-sig') as f:
        writer = csv.DictWriter(f, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)


@pytest_asyncio.fixture(scope="module", loop_scope="session")
async def layouts_context(isolated_state, uow_factory) -> dict:
    migration = await AccountBuilder(uow_factory=uow_factory).account_with_affiliations(ontology_role=OntologyRole.EDITOR)
    async with uow_factory.get_uow(user_id=migration['user_id']) as uow:
        layout_types = {
            name: (await uow.ontology.create_entry(LayoutTypeInput(name=name, axes=axes))).id
            for name, axes in (
                ("Row and Tree", [AxisType.ORDINAL] * 2),
            )
        }
        country_type = await uow.ontology.get_entry(name="Country", label=OntologyEntryLabel.LOCATION_TYPE)
        field_type = await uow.ontology.create_entry(LocationTypeInput(name="Field"))
        await uow.commit()

    async with uow_factory.get_uow(
            user_id=migration['user_id'], write_team=migration['team_id'], release=ReadRelease.PUBLIC
    ) as uow:
        region = await uow.repositories.regions.create(LocationInput(name="Nicaragua", code="NIC", type=country_type.id))
        for row in FIELDS:
            region.add_location(LocationInput(name=row['field'].strip('"'), type=field_type.id), parent_id=region.get_root_id())
        await uow.commit()
        field_locations = {
            row['field_uid']: next(
                location.id for location in region.yield_locations_by_type(field_type.id)
                if location.name == row['field'].strip('"')
            )
            for row in FIELDS
        }
    return {
        'context': MigrationContext(user_id=migration['user_id'], team_id=migration['team_id']),
        'layout_types': layout_types,
        'field_locations': field_locations
    }


@pytest.fixture
def data_dir(tmp_path, monkeypatch):
    write_csv(tmp_path / 'field_farm_region_country.csv', FIELDS)
    write_csv(tmp_path / 'field_layout_types.csv', LAYOUT_TYPES)
    write_csv(tmp_path / 'unit_positions.csv', POSITIONS)
    monkeypatch.setattr(layouts, 'BREEDCAFS_DATA_DIR', tmp_path)
    return tmp_path


@pytest.mark.asyncio(loop_scope="session")
async def test_prepare_layouts(uow_factory, layouts_context, data_dir):
    context = layouts_context['context']
    layout_types = layouts_context['layout_types']
    field_locations = layouts_context['field_locations']

    ids = await prepare_breedcafs_layouts(uow_factory, context, layout_types, field_locations)

    assert set(ids.layouts) == {
        ('1', '', ROW_AND_TREE),
        ('5', '', ROW_AND_TREE), ('5', 'July 2018 planting', ROW_AND_TREE),
        ('18', '', ROW_AND_TREE),
        ('29', 'Block A', ROW_AND_TREE), ('29', 'Block B', ROW_AND_TREE),
    }
    assert ids.created == 6

    async with uow_factory.get_uow(user_id=context.user_id) as uow:
        async def layout(key):
            return (await uow.repositories.arrangements.get(layout_id=ids.layouts[key])).root

        ed1 = await layout(('1', '', ROW_AND_TREE))
        assert (ed1.name, ed1.type, ed1.location, ed1.axes) == (
            "ED1: Row and Tree", layout_types["Row and Tree"], field_locations['1'], ["Row", "Tree"]
        )
        ed5 = await layout(('5', '', ROW_AND_TREE))
        assert (ed5.name, ed5.type, ed5.axes) == ("ED5: Row and Tree", layout_types["Row and Tree"], ["Row", "Tree"])
        planting = await layout(('5', 'July 2018 planting', ROW_AND_TREE))
        assert (planting.name, planting.location) == ("ED5 July 2018 planting: Row and Tree", field_locations['5'])
        block_a = await layout(('29', 'Block A', ROW_AND_TREE))
        assert (block_a.name, block_a.location) == ("La Cumplida Block A: Row and Tree", field_locations['29'])

        controller = await uow.controls.get_controller(ed1.label, ed1.id)
        assert controller.release is ReadRelease.PRIVATE
        assert set(controller.controls) == {context.team_id}

    with open(data_dir / 'layout_ids.csv') as f:
        rows = {(row['field_uid'], row['group'], row['layout_type']): int(row['layout_id']) for row in csv.DictReader(f)}
    assert rows == ids.layouts

    again = await prepare_breedcafs_layouts(uow_factory, context, layout_types, field_locations)
    assert again.created == 0
    assert again.layouts == ids.layouts


def test_tree_group():
    assert tree_group('29', 'block', 'Block A', 'Catimor') == 'Block A'
    assert tree_group('5', 'field', 'ED5', '7-ED6-1D2') == 'July 2018 planting'
    assert tree_group('5', 'field', 'ED5', 'Marsellesa') == ''
    assert tree_group('6', 'field', 'ED6', '7-ED6-1D2') == ''


@pytest.mark.skipif(
    not (BREEDCAFS_DATA_DIR / 'field_layout_types.csv').exists(),
    reason="The BreedCAFS layouts are not in the data directory"
)
def test_planned_layouts_cover_extracted_positions():
    planned = planned_layouts()
    with open(BREEDCAFS_DATA_DIR / 'item_name_subject_sources_sinks.csv', encoding='utf-8-sig') as f:
        names = {row['item_uid'].strip('"'): row['name'].strip('"') for row in csv.DictReader(f)}
    groups = {}
    with open(BREEDCAFS_DATA_DIR / 'unit_positions.csv', encoding='utf-8-sig') as f:
        for row in csv.DictReader(f):
            row = {key: value.strip('"') for key, value in row.items()}
            group = tree_group(row['field_uid'], row['layout_level'], row['layout_name'], names[row['item_uid']])
            assert (row['field_uid'], group, row['layout_type']) in planned
            groups.setdefault((row['field_uid'], group), []).append((row['row'], row['column']))
    # Positions are unique within each layout, except in field 5's July 2018 planting
    for (field_uid, group), positions in groups.items():
        if (field_uid, group) != ('5', 'July 2018 planting'):
            assert len(set(positions)) >= len(positions) - 3, (field_uid, group)
    assert len(groups[('5', 'July 2018 planting')]) == 1178
    assert len(set(groups[('5', '')])) == len(groups[('5', '')]) == 368
