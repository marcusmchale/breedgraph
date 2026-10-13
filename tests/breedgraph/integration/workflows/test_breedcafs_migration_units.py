import csv
import json

import pytest
import pytest_asyncio
from numpy import datetime64

from breedgraph.domain.model.accounts import OntologyRole
from breedgraph.domain.model.arrangements import LayoutInput
from breedgraph.domain.model.controls import ReadRelease
from breedgraph.domain.model.germplasm import GermplasmInput
from breedgraph.domain.model.ontology import SubjectInput, LocationTypeInput, LayoutTypeInput, OntologyEntryLabel, AxisType
from breedgraph.domain.model.regions import LocationInput

from breedcafs_migration import units
from breedcafs_migration.bootstrap import MigrationContext
from breedcafs_migration.layouts import LayoutIds, ROW_AND_TREE
from breedcafs_migration.locations import LocationIds
from breedcafs_migration.units import prepare_breedcafs_units, description

from tests.breedgraph.scenarios.account_builder import AccountBuilder


def item(uid, subject, name=None, sources=()):
    """As exported: values wrapped in extra quotes, fields as integer sources"""
    return {
        'item_uid': f'"""{uid}"""', 'name': f'"""{name}"""' if name else 'null', 'subject': f'"""{subject}"""',
        'source_items': json.dumps(list(sources)), 'sink_items': '[]'
    }


ITEMS = [
    item('1', 'Field', 'ED1'),
    item('1_B1', 'Block', 'Block 1', [1]),
    item('1_T1', 'Tree', 'Catimor', ['1_B1', 1]),
    item('1_T2', 'Tree', None, ['1_B1', 1]),
    item('1_S1', 'Branch', None, ['1_T1']),
    item('1_S2', 'Tree', None, ['1_B1']),           # a tree sample taken from the block
    item('1_S3', 'Branch', None, ['1_S2']),
    item('1_S4', 'Green Beans', '384-1', ['1_T1', '1_T2']),
    item('1_S6', 'Green Beans', '384-2', ['1_T1', '1_T3']),   # pooled from trees of different varieties
    item('1_T3', 'Tree', None, ['1_B1', 1]),
    item('1_S5', 'null', None, ['1_T1']),           # skipped
    item('25', 'Field', 'Parcel 1'),
    item('25_B1', 'Block', 'Shade', [25]),          # named after a treatment
    item('25_T1', 'Tree', None, ['25_B1', 25]),
    item('1_T9', 'Tree', 'Catimor', ['1_B1', 1]),      # a duplicate of 1_T1
]
FILES = {
    'item_name_subject_sources_sinks.csv': ITEMS,
    'skipped_items.csv': [{'item_uid': '1_S5', 'reason': 'Sample without a sample unit'}],
    'item_variety.csv': [
        {'item_uid': f'"""{uid}"""', 'variety': f'"""{variety}"""'}
        for uid, variety in (('1_T1', 'Catimor'), ('1_T2', 'Catimor'), ('1_T3', 'Caturra'), ('1_S4', 'Catimor'), ('1_S6', 'Catimor'))
    ],
    'unit_positions.csv': [
        {'field_uid': '1', 'item_uid': f'"""1_T{i}"""', 'layout_type': '"""row_and_tree"""', 'layout_level': '"""field"""',
         'layout_name': '"""ED1"""', 'row': '1.0', 'column': f'{i}.0', 'stratum': 'null'}
        for i in (1, 2)
    ],
    'branch_strata.csv': [{'item_uid': '1_S1', 'strata': '["Upper"]'}, {'item_uid': '1_S3', 'strata': '["Lower"]'}],
    'sample_positions.csv': [{'item_uid': '"""1_S4"""', 'location': '"""Montpellier/ IRD"""', 'date': '"""2019-03-25"""'}],
}


def write_csv(path, rows):
    with open(path, 'w', newline='', encoding='utf-8-sig') as f:
        writer = csv.DictWriter(f, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)


@pytest_asyncio.fixture(scope="module", loop_scope="session")
async def units_context(isolated_state, uow_factory) -> dict:
    migration = await AccountBuilder(uow_factory=uow_factory).account_with_affiliations(ontology_role=OntologyRole.EDITOR)
    user_id, team_id = migration['user_id'], migration['team_id']
    async with uow_factory.get_uow(user_id=user_id) as uow:
        subjects = {
            name: (await uow.ontology.create_entry(SubjectInput(name=name))).id
            for name in ("Field", "Trees", "Tree", "Branch", "Green Beans")
        }
        country_type = await uow.ontology.get_entry(name="Country", label=OntologyEntryLabel.LOCATION_TYPE)
        field_type = await uow.ontology.create_entry(LocationTypeInput(name="Field"))
        row_and_tree = await uow.ontology.create_entry(LayoutTypeInput(name="Row and Tree", axes=[AxisType.ORDINAL] * 2))
        await uow.commit()

    async with uow_factory.get_uow(user_id=user_id, write_team=team_id, release=ReadRelease.PUBLIC) as uow:
        region = await uow.repositories.regions.create(LocationInput(name="Viet Nam", code="VNM", type=country_type.id))
        for name in ("ED1", "Parcel 1", "IRD Montpellier"):
            region.add_location(LocationInput(name=name, type=field_type.id), parent_id=region.get_root_id())
        await uow.commit()
        location_ids = {location.name: location.id for location in region.yield_locations_by_type(field_type.id)}

    async with uow_factory.get_uow(user_id=user_id, write_team=team_id) as uow:
        layout_ids = {}
        for key, type_id, axes in (
                (('1', '', ROW_AND_TREE), row_and_tree.id, ["Row", "Tree"]),
        ):
            arrangement = await uow.repositories.arrangements.create(
                LayoutInput(name=str(key), type=type_id, location=location_ids["ED1"], axes=axes)
            )
            layout_ids[key] = arrangement.get_root_id()
        catimor = await uow.germplasm.create_entry(GermplasmInput(name="Catimor"))
        caturra = await uow.germplasm.create_entry(GermplasmInput(name="Caturra"))
        await uow.commit()

    return {
        'context': MigrationContext(user_id=user_id, team_id=team_id),
        'subjects': subjects,
        'germplasm': {"Catimor": catimor.id, "Caturra": caturra.id},
        'locations': LocationIds(
            fields={'1': location_ids["ED1"], '25': location_ids["Parcel 1"]},
            sample_locations={"Montpellier/ IRD": location_ids["IRD Montpellier"]}
        ),
        'layouts': LayoutIds(layouts=layout_ids),
    }


@pytest.fixture
def data_dir(tmp_path, monkeypatch):
    for name, rows in FILES.items():
        write_csv(tmp_path / name, rows)
    monkeypatch.setattr(units, 'BREEDCAFS_DATA_DIR', tmp_path)
    monkeypatch.setattr(units, 'DUPLICATE_ITEMS', {'1_T9': '1_T1'})
    return tmp_path


async def prepare(uow_factory, units_context):
    return await prepare_breedcafs_units(
        uow_factory, units_context['context'], units_context['subjects'], units_context['germplasm'],
        units_context['locations'], units_context['layouts']
    )


@pytest.mark.asyncio(loop_scope="session")
async def test_prepare_units(uow_factory, units_context, data_dir):
    context = units_context['context']
    subjects = units_context['subjects']
    layouts = units_context['layouts'].layouts

    ids = await prepare(uow_factory, units_context)

    # Not the skipped sample, nor the block named after a treatment
    assert set(ids.units) == {'1', '1_B1', '1_T1', '1_T2', '1_T3', '1_S1', '1_S2', '1_S3', '1_S4', '1_S6', '25', '25_T1'}
    assert ids.created == 12
    assert ids.factor_records == [('1_S1', 'Stratum', 'Upper'), ('1_S3', 'Stratum', 'Lower'), ('25_T1', 'Shade Treatment', 'Shade')]

    async with uow_factory.get_uow(user_id=context.user_id) as uow:
        block = await uow.repositories.blocks.get(unit_id=ids.units['1'])
        unit = lambda uid: block.get_unit(ids.units[uid])
        parents = lambda uid: set(block.get_parent_ids(ids.units[uid]))

        assert block.get_root_id() == ids.units['1']
        field_unit = unit('1')
        assert (field_unit.name, field_unit.subject, field_unit.description) == ("ED1", subjects["Field"], "BreedCAFS item 1")
        assert [p.location_id for p in field_unit.positions] == [units_context['locations'].fields['1']]

        assert unit('1_B1').subject == subjects["Trees"]
        assert parents('1_B1') == {ids.units['1']}
        assert parents('1_T1') == {ids.units['1_B1']}
        assert parents('1_S4') == {ids.units['1_T1'], ids.units['1_T2']}

        tree = unit('1_T1')
        assert (tree.name, tree.germplasm) == ("Catimor", units_context['germplasm']["Catimor"])
        assert [(p.layout_id, p.coordinates) for p in tree.positions] == [(layouts[('1', '', ROW_AND_TREE)], ["1", "1"])]
        assert unit('1_T2').name == '1_T2'

        branch = unit('1_S1')
        assert branch.subject == subjects["Branch"]
        assert branch.positions == []
        assert parents('1_S1') == {ids.units['1_T1']}

        # Pooled from trees of one variety: its own; of different varieties: none, as its parents say what it contains
        assert unit('1_S4').germplasm == units_context['germplasm']["Catimor"]
        assert unit('1_S6').germplasm is None
        assert parents('1_S6') == {ids.units['1_T1'], ids.units['1_T3']}

        beans = unit('1_S4')
        assert [(p.location_id, p.start) for p in beans.positions] == [
            (units_context['locations'].sample_locations["Montpellier/ IRD"], datetime64('2019-03-25'))
        ]

        controller = await uow.controls.get_controller(tree.label, tree.id)
        assert controller.release is ReadRelease.PRIVATE
        assert set(controller.controls) == {context.team_id}

        shade = await uow.repositories.blocks.get(unit_id=ids.units['25'])
        assert set(shade.get_parent_ids(ids.units['25_T1'])) == {ids.units['25']}
        assert shade.get_unit(ids.units['25_T1']).description == description('25_T1')

    with open(data_dir / 'unit_ids.csv') as f:
        assert {row['item_uid']: int(row['unit_id']) for row in csv.DictReader(f)} == ids.units
    with open(data_dir / 'factor_records.csv') as f:
        assert [tuple(row.values()) for row in csv.DictReader(f)] == ids.factor_records

    again = await prepare(uow_factory, units_context)
    assert again.created == 0
    assert again.units == ids.units
