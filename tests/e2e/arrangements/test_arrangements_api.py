import pytest

from src.breedgraph.custom_exceptions import NoResultFoundError
from tests.conftest import lorem_text_generator

from tests.e2e.arrangements.post_methods import post_to_add_layout, post_to_arrangements, post_to_layout

from tests.e2e.ontologies.post_methods import post_to_add_entry, post_to_get_entries
from tests.e2e.payload_helpers import get_verified_payload, assert_payload_success

@pytest.mark.usefixtures("session_database")
@pytest.mark.asyncio(scope="session")
async def test_create_layout(
        client,
        first_user_login_token,
        first_account_with_all_affiliations,
        basic_ontology,
        basic_region,
        lorem_text_generator
):
    field_type_id, field_type = basic_ontology.get_entry(entry="Field", label="LocationType")
    field = next(basic_region.yield_locations_by_type(field_type_id))

    indexed_rows_type_id, indexed_rows_type = basic_ontology.get_entry(entry="Indexed Rows", label="LayoutType")
    layout_name = lorem_text_generator.new_text(10)
    layout = {
        'release': "REGISTERED",
        'name': layout_name,
        'location': field.id,
        'type': indexed_rows_type_id,
        'axes': ["row", "index"]
    }
    add_response = await post_to_add_layout(
        client,
        token=first_user_login_token,
        layout=layout
    )
    add_payload = get_verified_payload(add_response, "add_layout")
    assert_payload_success(add_payload)

    arrangements_request_response = await post_to_arrangements(client, token=first_user_login_token)
    arrangements_payload = get_verified_payload(arrangements_request_response, "arrangements")
    assert arrangements_payload.get('result')[0].get('name') == layout_name

    arrangements_at_location_request_response = await post_to_arrangements(client, location_id=field.id, token=first_user_login_token)
    arrangements_at_location_payload = get_verified_payload(arrangements_at_location_request_response, "arrangements")
    assert arrangements_at_location_payload.get('result')[0].get('name') == layout_name
    assert arrangements_at_location_payload.get('result')[0].get('type').get('id') == indexed_rows_type_id

    layout_id = arrangements_at_location_payload.get('result')[0].get('id')

    layout_request_response = await post_to_layout(client, layout_id=layout_id, token=first_user_login_token)
    layout_payload = get_verified_payload(layout_request_response, "layout")
    assert layout_payload.get('result').get('name') == layout_name
    assert layout_payload.get('result').get('type').get('id') == indexed_rows_type_id

@pytest.mark.asyncio(scope="session")
async def test_extended_layout(
        client,
        first_user_login_token,
        first_account_with_all_affiliations,
        basic_ontology,
        basic_region,
        lorem_text_generator
):

    lab_type_id, lab_type = basic_ontology.get_entry(entry="Lab", label="LocationType")
    lab = next(basic_region.yield_locations_by_type(lab_type_id))

    numbered_type_id, numbered_type = basic_ontology.get_entry(entry="Numbered", label="LayoutType")
    facility_layout_name = "Growth Facility"
    facility_layout = {
        'release': "REGISTERED",
        'name': facility_layout_name,
        'location': lab.id,
        'type': numbered_type_id,
        'axes': ["Chamber"]
    }
    add_facility_response = await post_to_add_layout(
        client,
        token=first_user_login_token,
        layout=facility_layout
    )
    add_facility_payload = get_verified_payload(add_facility_response, "add_layout")
    assert_payload_success(add_facility_payload)

    arrangements_request_response = await post_to_arrangements(client, location_id=lab.id, token=first_user_login_token)
    arrangements_payload = get_verified_payload(arrangements_request_response, "arrangements")
    arrangements = arrangements_payload.get('result')
    assert len(arrangements) == 1
    facility_layout = arrangements[0]
    facility_layout_id = facility_layout.get('id')

    adjacency_3d_type_id, adjacency_3d_type = basic_ontology.get_entry(entry="3D Adjacency", label="LayoutType")
    chamber_layout_name = "Chamber 1"
    growth_chamber_position = 1
    chamber_layout = {
        'release': "PRIVATE",
        'name': chamber_layout_name,
        'location': lab.id,
        'type': adjacency_3d_type_id,
        'axes': ["Depth","Vertical", "Horizontal"],
        'parent': facility_layout_id,
        'position': [{'integer':growth_chamber_position}]
    }
    add_chamber_response = await post_to_add_layout(
        client,
        token=first_user_login_token,
        layout=chamber_layout
    )
    add_chamber_payload = get_verified_payload(add_chamber_response, "add_layout")
    assert_payload_success(add_chamber_payload)

    facility_layout_request_response = await post_to_layout(client, layout_id=facility_layout_id, token=first_user_login_token)
    facility_layout_payload = get_verified_payload(facility_layout_request_response, "layout")
    facility_layout = facility_layout_payload.get('result')
    assert len(facility_layout.get('children')) == 1
    chamber_layout = facility_layout.get('children')[0]
    chamber_layout_id = chamber_layout.get('id')

    grid_type_id, grid_type = basic_ontology.get_entry(entry="Grid", label="LayoutType")
    shelf_layout_name = "Rear-Top-Right Shelf"
    shelf_layout = {
        'release': "PRIVATE",
        'name': shelf_layout_name,
        'location': lab.id,
        'type': grid_type_id,
        'axes': ["column","row"],
        'parent': chamber_layout_id,
        'position': [{'string': 'rear'}, {'string': 'top'}, {'string': 'right'}]
    }
    add_shelf_response = await post_to_add_layout(
        client,
        token=first_user_login_token,
        layout=shelf_layout
    )
    add_shelf_payload = get_verified_payload(add_shelf_response, "add_layout")
    assert_payload_success(add_shelf_payload)

    chamber_layout_request_response = await post_to_layout(client, layout_id=chamber_layout_id, token=first_user_login_token)
    chamber_layout_payload = get_verified_payload(chamber_layout_request_response, "layout")
    chamber_layout = chamber_layout_payload.get('result')

    assert len(chamber_layout.get('children')) == 1
    shelf_layout = chamber_layout.get('children')[0]
    assert shelf_layout.get('id')
