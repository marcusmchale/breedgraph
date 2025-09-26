import pytest

from src.breedgraph.custom_exceptions import NoResultFoundError
from tests.conftest import lorem_text_generator
from src.breedgraph.domain.model.ontology import OntologyEntryLabel

from tests.e2e.arrangements.post_methods import post_to_create_layout, post_to_arrangements, post_to_layout
from tests.e2e.regions.post_methods import post_to_locations
from tests.e2e.ontologies.post_methods import post_to_get_entries
from tests.e2e.utils import get_verified_payload, assert_payload_success

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
    field_type_ontology_response = await post_to_get_entries(client=client, token=first_user_login_token, names=["Field"], labels=[OntologyEntryLabel.LOCATION_TYPE])
    field_type_ontology_payload = get_verified_payload(field_type_ontology_response, "ontologyEntries")
    field_type_id = field_type_ontology_payload.get('result')[0].get('id')

    locations_response = await post_to_locations(client=client, token=first_user_login_token, location_type_id = field_type_id)
    locations_payload = get_verified_payload(locations_response, "regionsLocations")
    field_location_id = locations_payload.get('result')[0].get('id')

    index_rows_ontology_response = await post_to_get_entries(client=client, token=first_user_login_token, names=["Indexed Rows"], labels=[OntologyEntryLabel.LAYOUT_TYPE])
    index_rows_ontology_payload = get_verified_payload(index_rows_ontology_response, "ontologyEntries")
    indexed_rows_type_id = index_rows_ontology_payload.get('result')[0].get('id')

    layout_name = lorem_text_generator.new_text(10)
    layout = {
        'name': layout_name,
        'locationId': field_location_id,
        'typeId': indexed_rows_type_id,
        'axes': ["row", "index"]
    }
    create_layout_response = await post_to_create_layout(
        client,
        token=first_user_login_token,
        layout=layout
    )
    create_layout_payload = get_verified_payload(create_layout_response, "arrangementsCreateLayout")
    assert_payload_success(create_layout_payload)

    arrangements_request_response = await post_to_arrangements(client, token=first_user_login_token)
    arrangements_payload = get_verified_payload(arrangements_request_response, "arrangements")
    assert arrangements_payload.get('result')[0].get('name') == layout_name

    arrangements_at_location_request_response = await post_to_arrangements(client, location_id=field_location_id, token=first_user_login_token)
    arrangements_at_location_payload = get_verified_payload(arrangements_at_location_request_response, "arrangements")
    assert arrangements_at_location_payload.get('result')[0].get('name') == layout_name
    assert arrangements_at_location_payload.get('result')[0].get('type').get('id') == indexed_rows_type_id

    layout_id = arrangements_at_location_payload.get('result')[0].get('id')

    layout_request_response = await post_to_layout(client, layout_id=layout_id, token=first_user_login_token)
    layout_payload = get_verified_payload(layout_request_response, "arrangementsLayout")
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
    lab_type_ontology_response = await post_to_get_entries(
        client=client, token=first_user_login_token,
        names=["Laboratory"], labels=[OntologyEntryLabel.LOCATION_TYPE]
    )
    lab_type_ontology_payload = get_verified_payload(lab_type_ontology_response, "ontologyEntries")
    lab_type_id = lab_type_ontology_payload.get('result')[0].get('id')

    lab_location_response = await post_to_locations(
        client=client, token=first_user_login_token, location_type_id = lab_type_id
    )
    lab_location_payload = get_verified_payload(lab_location_response, "regionsLocations")
    lab_id = lab_location_payload.get('result')[0].get('id')

    numbered_type_ontology_response = await post_to_get_entries(
        client=client, token=first_user_login_token,
        names=["Numbered"], labels=[OntologyEntryLabel.LAYOUT_TYPE]
    )
    numbered_type_ontology_payload = get_verified_payload(numbered_type_ontology_response, "ontologyEntries")
    numbered_type_id = numbered_type_ontology_payload.get('result')[0].get('id')

    facility_layout_name = "Growth Facility"
    facility_layout = {
        'name': facility_layout_name,
        'locationId': lab_id,
        'typeId': numbered_type_id,
        'axes': ["Chamber"]
    }
    create_facility_response = await post_to_create_layout(
        client,
        token=first_user_login_token,
        layout=facility_layout
    )
    create_facility_payload = get_verified_payload(create_facility_response, "arrangementsCreateLayout")
    assert_payload_success(create_facility_payload)

    arrangements_request_response = await post_to_arrangements(client, location_id=lab_id, token=first_user_login_token)
    arrangements_payload = get_verified_payload(arrangements_request_response, "arrangements")
    arrangements = arrangements_payload.get('result')
    assert len(arrangements) == 1
    facility_layout = arrangements[0]
    facility_layout_id = facility_layout.get('id')

    adjacency_3d_type_ontology_response = await post_to_get_entries(
        client=client, token=first_user_login_token,
        names=["3D Adjacency"], labels=[OntologyEntryLabel.LAYOUT_TYPE]
    )
    adjacency_3d_type_ontology_payload = get_verified_payload(adjacency_3d_type_ontology_response, "ontologyEntries")
    adjacency_3d_type_id = adjacency_3d_type_ontology_payload.get('result')[0].get('id')

    chamber_layout_name = "Chamber 1"
    facility_position = "1"
    chamber_layout = {
        'name': chamber_layout_name,
        'locationId': lab_id,
        'typeId': adjacency_3d_type_id,
        'axes': ["Depth","Vertical", "Horizontal"],
        'parentId': facility_layout_id,
        'position': [facility_position]
    }
    create_chamber_response = await post_to_create_layout(
        client,
        token=first_user_login_token,
        layout=chamber_layout
    )
    create_chamber_payload = get_verified_payload(create_chamber_response, "arrangementsCreateLayout")
    assert_payload_success(create_chamber_payload)

    facility_layout_request_response = await post_to_layout(client, layout_id=facility_layout_id, token=first_user_login_token)
    facility_layout_payload = get_verified_payload(facility_layout_request_response, "arrangementsLayout")
    facility_layout = facility_layout_payload.get('result')
    assert len(facility_layout.get('children')) == 1
    chamber_layout = facility_layout.get('children')[0]
    chamber_layout_id = chamber_layout.get('id')

    grid_type_ontology_response = await post_to_get_entries(
        client=client, token=first_user_login_token,
        names=["Grid"], labels=[OntologyEntryLabel.LAYOUT_TYPE]
    )
    grid_type_ontology_payload = get_verified_payload(grid_type_ontology_response, "ontologyEntries")
    grid_type_id = grid_type_ontology_payload.get('result')[0].get('id')

    shelf_layout_name = "Rear-Top-Right Shelf"
    shelf_layout = {
        'name': shelf_layout_name,
        'locationId': lab_id,
        'typeId': grid_type_id,
        'axes': ["column","row"],
        'parentId': chamber_layout_id,
        'position': ['rear', 'top', 'right']
    }
    create_shelf_response = await post_to_create_layout(
        client,
        token=first_user_login_token,
        layout=shelf_layout
    )
    create_shelf_payload = get_verified_payload(create_shelf_response, "arrangementsCreateLayout")
    assert_payload_success(create_shelf_payload)

    chamber_layout_request_response = await post_to_layout(client, layout_id=chamber_layout_id, token=first_user_login_token)
    chamber_layout_payload = get_verified_payload(chamber_layout_request_response, "arrangementsLayout")
    chamber_layout = chamber_layout_payload.get('result')

    assert len(chamber_layout.get('children')) == 1
    shelf_layout = chamber_layout.get('children')[0]
    assert shelf_layout.get('id')
