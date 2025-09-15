import pytest

from tests.e2e.blocks.post_methods import post_to_add_unit, post_to_blocks, post_to_unit, post_to_add_position
from tests.e2e.ontologies.post_methods import post_to_get_entries
from tests.e2e.utils import get_verified_payload, assert_payload_success

@pytest.mark.usefixtures("session_database")
@pytest.mark.asyncio(scope="session")
async def test_create_unit(
        client,
        first_user_login_token,
        first_account_with_all_affiliations,
        basic_ontology_service
):
    tree_subject_response = await post_to_get_entries(client, token=first_user_login_token, name= "tree", label="Subject")
    subject_payload = get_verified_payload(tree_subject_response, "ontology_entries")
    subject_id = subject_payload.get('result')[0].get('id')

    unit_input = {
        'subject': subject_id,
        'name': "New Tree",
        'release': "REGISTERED"
    }

    response = await post_to_add_unit(client, first_user_login_token, unit=unit_input)
    payload = get_verified_payload(response, "blocks_add_unit")
    assert_payload_success(payload)

@pytest.mark.asyncio(scope="session")
async def test_extend_block(
        client,
        first_user_login_token,
        first_account_with_all_affiliations,
        basic_ontology_service
):
    blocks_response = await post_to_blocks(client, first_user_login_token)
    blocks_payload = get_verified_payload(blocks_response, "blocks")
    assert blocks_payload.get('result')
    tree_unit_id = blocks_payload.get('result')[0].get('id')

    tree_unit_response = await post_to_unit(client, unit_id=tree_unit_id, token=first_user_login_token)
    tree_unit_payload = get_verified_payload(tree_unit_response, "unit")
    assert tree_unit_payload.get('result')

    rhizosphere_subject_response = await post_to_get_entries(
        client,
        token=first_user_login_token,
        name="rhizosphere",
        label="Subject"
    )
    rhizosphere_subject_payload = get_verified_payload(rhizosphere_subject_response, "ontology_entries")
    rhizosphere_subject_id = rhizosphere_subject_payload.get('result')[0].get('id')

    rhizosphere_unit_input = {
        'subject': rhizosphere_subject_id,
        'name': "New Tree",
        'parents':[tree_unit_id],
        'release': 'PRIVATE'
    }
    add_rhizosphere_response = await post_to_add_unit(client, first_user_login_token, unit=rhizosphere_unit_input)
    add_rhizosphere_payload = get_verified_payload(add_rhizosphere_response, "blocks_add_unit")
    assert_payload_success(add_rhizosphere_payload)

    field_subject_response = await post_to_get_entries(
        client,
        token=first_user_login_token,
        name="field",
        label="Subject"
    )
    field_subject_payload = get_verified_payload(field_subject_response, "ontology_entries")
    field_subject_id = field_subject_payload.get('result')[0].get('id')

    field_unit_input = {
        'subject': field_subject_id,
        'name': "Small Field",
        'release': 'PUBLIC',
        'children': [tree_unit_id]
    }
    add_field_response = await post_to_add_unit(client, first_user_login_token, unit=field_unit_input)
    add_field_payload = get_verified_payload(add_field_response, "blocks_add_unit")
    assert_payload_success(add_field_payload)

@pytest.mark.asyncio(scope="session")
async def test_add_unit_position(
        client,
        first_user_login_token,
        first_account_with_all_affiliations,
        basic_ontology_service,
        basic_region,
        field_arrangement
):
    blocks_response = await post_to_blocks(client, first_user_login_token)
    blocks_payload = get_verified_payload(blocks_response, "blocks")
    assert blocks_payload.get('result')
    tree_unit_id = blocks_payload.get('result')[0].get('id')

    location_type_id, location_type = basic_ontology_service.get_entry("Field", "LocationType")
    field = next(basic_region.yield_locations_by_type(location_type_id))

    position = {
        'location': field.id,
        'layout': field_arrangement.root.id,
        'coordinates': ["1", "A"],
        'start': '2023'
    }
    add_position_response = await post_to_add_position(client, first_user_login_token, unit_id=tree_unit_id, position=position)
    add_position_payload = get_verified_payload(add_position_response, "blocks_add_position")
    assert_payload_success(add_position_payload)