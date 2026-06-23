import pytest

from tests.e2e.arrangements.post_methods import post_to_create_layout, post_to_arrangements, post_to_layouts
from tests.e2e.utils import get_verified_payload, assert_payload_success

@pytest.mark.asyncio(loop_scope="session")
async def test_create_layout(
        layout_build_context,
        login_token_factory,
        client,
        lorem_text_generator
):
    user_id = layout_build_context['user_id']
    login_token = login_token_factory(user_id=user_id)
    location_id = layout_build_context['location_id']
    type_id = layout_build_context['ontology_layout_grid']
    layout_name = lorem_text_generator.new_text(10)
    layout = {
        'name': layout_name,
        'locationId': location_id,
        'typeId': type_id,
        'axes': ["row", "index"]
    }
    create_layout_response = await post_to_create_layout(
        client,
        token=login_token,
        layout=layout
    )
    create_layout_payload = get_verified_payload(create_layout_response, "arrangementsCreateLayout")

    assert_payload_success(create_layout_payload)

    arrangements_request_response = await post_to_arrangements(client, token=login_token)
    arrangements_payload = get_verified_payload(arrangements_request_response, "arrangements")
    assert arrangements_payload.get('result')[0].get('name') == layout_name

    arrangements_at_location_request_response = await post_to_arrangements(client, location_id=location_id, token=login_token)
    arrangements_at_location_payload = get_verified_payload(arrangements_at_location_request_response, "arrangements")
    assert arrangements_at_location_payload.get('result')[0].get('name') == layout_name
    assert arrangements_at_location_payload.get('result')[0].get('type').get('id') == type_id

    layout_id = arrangements_at_location_payload.get('result')[0].get('id')

    layout_request_response = await post_to_layouts(client, layout_ids=[layout_id], token=login_token)
    layout_payload = get_verified_payload(layout_request_response, "arrangementsLayouts")
    assert layout_payload.get('result')[0].get('name') == layout_name
    assert layout_payload.get('result')[0].get('type').get('id') == type_id

@pytest.mark.asyncio(loop_scope="session")
async def test_extended_layout(
        layout_build_context,
        login_token_factory,
        client,
        lorem_text_generator
):
    user_id = layout_build_context['user_id']
    login_token = login_token_factory(user_id=user_id)
    location_id = layout_build_context['location_id']
    named_type_id = layout_build_context['ontology_layout_named']
    adjacency_3d_type_id = layout_build_context['ontology_layout_3d']
    grid_type_id = layout_build_context['ontology_layout_grid']

    facility_layout_name = "Growth Facility"
    facility_layout = {
        'name': facility_layout_name,
        'locationId': location_id,
        'typeId': named_type_id,
        'axes': ["Chamber"]
    }
    create_facility_response = await post_to_create_layout(
        client,
        token=login_token,
        layout=facility_layout
    )
    create_facility_payload = get_verified_payload(create_facility_response, "arrangementsCreateLayout")
    assert_payload_success(create_facility_payload)

    arrangements_request_response = await post_to_arrangements(client, location_id=location_id, token=login_token)
    arrangements_payload = get_verified_payload(arrangements_request_response, "arrangements")
    arrangements = arrangements_payload.get('result')

    facility_layout = [i for i in arrangements if i.get('name') == facility_layout_name] [0]
    facility_layout_id = facility_layout.get('id')

    chamber_layout_name = "Chamber 1"
    facility_position = "1"
    chamber_layout = {
        'name': chamber_layout_name,
        'locationId': location_id,
        'typeId': adjacency_3d_type_id,
        'axes': ["Depth","Vertical", "Horizontal"],
        'parentId': facility_layout_id,
        'position': [facility_position]
    }
    create_chamber_response = await post_to_create_layout(
        client,
        token=login_token,
        layout=chamber_layout
    )
    create_chamber_payload = get_verified_payload(create_chamber_response, "arrangementsCreateLayout")
    assert_payload_success(create_chamber_payload)

    facility_layout_request_response = await post_to_layouts(client, layout_ids=[facility_layout_id], token=login_token)
    facility_layout_payload = get_verified_payload(facility_layout_request_response, "arrangementsLayouts")
    facility_layout = facility_layout_payload.get('result')[0]
    assert len(facility_layout.get('children')) == 1
    chamber_layout = facility_layout.get('children')[0]
    chamber_layout_id = chamber_layout.get('id')

    shelf_layout_name = "Rear-Top-Right Shelf"
    shelf_layout = {
        'name': shelf_layout_name,
        'locationId': location_id,
        'typeId': grid_type_id,
        'axes': ["column","row"],
        'parentId': chamber_layout_id,
        'position': ['rear', 'top', 'right']
    }
    create_shelf_response = await post_to_create_layout(
        client,
        token=login_token,
        layout=shelf_layout
    )
    create_shelf_payload = get_verified_payload(create_shelf_response, "arrangementsCreateLayout")
    assert_payload_success(create_shelf_payload)

    chamber_layout_request_response = await post_to_layouts(client, layout_ids=[chamber_layout_id], token=login_token)
    chamber_layout_payload = get_verified_payload(chamber_layout_request_response, "arrangementsLayouts")
    chamber_layout = chamber_layout_payload.get('result')[0]

    assert len(chamber_layout.get('children')) == 1
    shelf_layout = chamber_layout.get('children')[0]
    assert shelf_layout.get('id')
