import csv
import shutil

import pytest
import pytest_asyncio

from breedgraph.domain.model.accounts import OntologyRole
from breedgraph.domain.model.controls import ReadRelease
from breedgraph.domain.model.ontology import LocationTypeInput, OntologyEntryLabel
from breedgraph.domain.model.location_trees import LocationInput, LocationOutput

from breedcafs_migration import locations
from breedcafs_migration.bootstrap import MigrationContext
from breedcafs_migration.locations import prepare_breedcafs_locations, read_fields
from breedcafs_migration.setup.config import BREEDCAFS_DATA_DIR

from tests.breedgraph.scenarios.account_builder import AccountBuilder

# As exported: values wrapped in extra quotes
FIELDS = [
    {'field_uid': '1', 'field': '"""Field A"""', 'farm': '"""Farm 1"""', 'region': '"""Matagalpa"""', 'country': '"""Nicaragua"""'},
    {'field_uid': '2', 'field': '"""Field B"""', 'farm': '"""Farm 1"""', 'region': '"""Matagalpa"""', 'country': '"""Nicaragua"""'},
    {'field_uid': '35', 'field': '"""Room 2"""', 'farm': '"""Greenhouse"""', 'region': '"""Copenhagen"""', 'country': '"""Denmark"""'},
]
COORDINATES = [{'field_uid': '1', 'lat': '"""12.9"""', 'long': '"""-85.9"""'}]
SAMPLE_POSITIONS = [
    {'item_uid': '"""36_S5"""', 'location': '"""Montpellier/ IRD"""', 'date': '"""2019-03-25"""'},
    {'item_uid': '"""36_S3"""', 'location': '"""Montpellier/ IRD"""', 'date': '"""2019-03-25"""'},
]


def write_csv(path, rows):
    with open(path, 'w', newline='', encoding='utf-8-sig') as f:
        writer = csv.DictWriter(f, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)


@pytest_asyncio.fixture(scope="module", loop_scope="session")
async def locations_context(isolated_state, uow_factory) -> dict:
    account_builder = AccountBuilder(uow_factory=uow_factory)
    migration = await account_builder.account_with_affiliations(ontology_role=OntologyRole.EDITOR)
    others = await account_builder.account_with_affiliations()

    async with uow_factory.get_uow(user_id=migration['user_id']) as uow:
        location_types = {
            "Country": (await uow.ontology.get_entry(name="Country", label=OntologyEntryLabel.LOCATION_TYPE)).id
        }
        for name in ("Region", "Farm", "Field", "Research Center"):
            location_types[name] = (await uow.ontology.create_entry(LocationTypeInput(name=name))).id
        await uow.commit()

    # A country another team has already registered
    async with uow_factory.get_uow(user_id=others['user_id'], write_team=others['team_id'], release=ReadRelease.PUBLIC) as uow:
        location_tree = await uow.repositories.location_trees.create(
            LocationInput(name="Nicaragua", code="NIC", type=location_types["Country"])
        )
        await uow.commit()

    return {
        'context': MigrationContext(user_id=migration['user_id'], team_id=migration['team_id']),
        'location_types': location_types,
        'nicaragua_id': location_tree.get_root_id()
    }


@pytest.mark.asyncio(loop_scope="session")
async def test_prepare_locations(uow_factory, state_store, locations_context, tmp_path, monkeypatch):
    write_csv(tmp_path / 'field_farm_region_country.csv', FIELDS)
    write_csv(tmp_path / 'field_lat_long.csv', COORDINATES)
    write_csv(tmp_path / 'sample_positions.csv', SAMPLE_POSITIONS)
    monkeypatch.setattr(locations, 'BREEDCAFS_DATA_DIR', tmp_path)
    context = locations_context['context']

    ids = await prepare_breedcafs_locations(uow_factory, context, locations_context['location_types'])

    assert ids.countries["Nicaragua"] == locations_context['nicaragua_id']
    assert ids.countries_created == {"Denmark", "France"}
    # Denmark, France, 2 regions, 2 farms, 3 fields and the research center
    assert ids.created == 10
    assert set(ids.sample_locations) == {"Montpellier/ IRD"}
    assert set(ids.fields) == {'1', '2', '35'}
    assert len(set(ids.fields.values())) == 3

    async with uow_factory.get_uow(user_id=context.user_id) as uow:
        nicaragua = await uow.repositories.location_trees.get(location_id=ids.countries["Nicaragua"])
        field_a = nicaragua.get_location(ids.fields['1'])
        assert field_a.name == "Field A"
        assert field_a.type == locations_context['location_types']["Field"]
        assert [(c['latitude'], c['longitude']) for c in field_a.coordinates] == [(12.9, -85.9)]
        farm_id = nicaragua.get_parent_id(field_a.id)
        assert nicaragua.get_parent_id(ids.fields['2']) == farm_id
        assert nicaragua.get_location(nicaragua.get_parent_id(farm_id)).name == "Matagalpa"

        controller = await uow.controls.get_controller(field_a.label, field_a.id)
        assert controller.release is ReadRelease.PRIVATE
        assert set(controller.controls) == {context.team_id}
        denmark = await uow.controls.get_controller(field_a.label, ids.countries["Denmark"])
        assert denmark.release is ReadRelease.PUBLIC

        france = await uow.repositories.location_trees.get(location_id=ids.countries["France"])
        assert france.root.code == "FRA"
        ird = france.get_location(ids.sample_locations["Montpellier/ IRD"])
        assert ird.name == "IRD Montpellier"
        assert ird.type == locations_context['location_types']["Research Center"]
        assert france.get_parent_id(ird.id) == france.get_root_id()

    with open(tmp_path / 'location_ids.csv') as f:
        assert {row['field_uid']: int(row['location_id']) for row in csv.DictReader(f)} == ids.fields

    # the API sees the created countries as stored
    denmark = await state_store.get_country('DNK')
    assert isinstance(denmark, LocationOutput) and denmark.id == ids.countries["Denmark"]

    again = await prepare_breedcafs_locations(uow_factory, context, locations_context['location_types'])
    assert again.created == 0
    assert again.fields == ids.fields


@pytest.mark.asyncio(loop_scope="session")
@pytest.mark.skipif(
    not (BREEDCAFS_DATA_DIR / 'field_farm_region_country.csv').exists(),
    reason="The BreedCAFS locations are not in the data directory"
)
async def test_prepare_locations_from_extracted_fields(uow_factory, locations_context, tmp_path, monkeypatch):
    for name in ('field_farm_region_country.csv', 'field_lat_long.csv', 'sample_positions.csv'):
        shutil.copy(BREEDCAFS_DATA_DIR / name, tmp_path / name)
    monkeypatch.setattr(locations, 'BREEDCAFS_DATA_DIR', tmp_path)

    ids = await prepare_breedcafs_locations(uow_factory, locations_context['context'], locations_context['location_types'])
    assert set(ids.fields) == {row['field_uid'] for row in read_fields()}
    assert len(set(ids.fields.values())) == len(ids.fields)
