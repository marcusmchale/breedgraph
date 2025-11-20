import pytest

from src.breedgraph.domain.model.ontology import OntologyEntryLabel
from tests.e2e.blocks.post_methods import post_to_create_unit, post_to_blocks, post_to_units, post_to_add_position
from tests.e2e.ontologies.post_methods import post_to_get_entries
from tests.e2e.organisations.post_methods import post_to_create_team
from tests.e2e.utils import get_verified_payload, assert_payload_success

@pytest.mark.usefixtures("session_database")
@pytest.mark.asyncio(scope="session")
async def test_create_unit(
        client,
        first_user_login_token,
        first_account_with_all_affiliations,
        basic_ontology
):
    tree_subject_response = await post_to_get_entries(client, token=first_user_login_token, names= ["tree"], labels=[OntologyEntryLabel.SUBJECT])
    subject_payload = get_verified_payload(tree_subject_response, "ontologyEntries")
    subject_id = subject_payload.get('result')[0].get('id')

    unit_input = {
        'subjectId': subject_id,
        'name': "New Tree"
    }
    response = await post_to_create_unit(client, first_user_login_token, unit=unit_input)
    payload = get_verified_payload(response, "blocksCreateUnit")
    assert_payload_success(payload)

@pytest.mark.asyncio(scope="session")
async def test_extend_block(
        client,
        first_user_login_token,
        first_account_with_all_affiliations,
        basic_ontology
):
    blocks_response = await post_to_blocks(client, first_user_login_token)
    blocks_payload = get_verified_payload(blocks_response, "blocks")
    assert blocks_payload.get('result')
    tree_unit_id = blocks_payload.get('result')[0].get('id')

    tree_unit_response = await post_to_units(client, unit_ids=[tree_unit_id], token=first_user_login_token)
    tree_unit_payload = get_verified_payload(tree_unit_response, "blocksUnit")
    assert tree_unit_payload.get('result')

    rhizosphere_subject_response = await post_to_get_entries(
        client,
        token=first_user_login_token,
        names=["rhizosphere"],
        labels=[OntologyEntryLabel.SUBJECT]
    )
    rhizosphere_subject_payload = get_verified_payload(rhizosphere_subject_response, "ontologyEntries")
    rhizosphere_subject_id = rhizosphere_subject_payload.get('result')[0].get('id')

    rhizosphere_unit_input = {
        'subjectId': rhizosphere_subject_id,
        'name': "New Tree",
        'parentIds':[tree_unit_id]
    }
    add_rhizosphere_response = await post_to_create_unit(client, first_user_login_token, unit=rhizosphere_unit_input)
    add_rhizosphere_payload = get_verified_payload(add_rhizosphere_response, "blocksCreateUnit")
    assert_payload_success(add_rhizosphere_payload)

    field_subject_response = await post_to_get_entries(
        client,
        token=first_user_login_token,
        names=["field"],
        labels=[OntologyEntryLabel.SUBJECT]
    )
    field_subject_payload = get_verified_payload(field_subject_response, "ontologyEntries")
    field_subject_id = field_subject_payload.get('result')[0].get('id')

    field_unit_input = {
        'subjectId': field_subject_id,
        'name': "Small Field",
        'childrenIds': [tree_unit_id]
    }
    add_field_response = await post_to_create_unit(client, first_user_login_token, unit=field_unit_input)
    add_field_payload = get_verified_payload(add_field_response, "blocksCreateUnit")
    assert_payload_success(add_field_payload)

@pytest.mark.asyncio(scope="session")
async def test_add_unit_position(
        client,
        first_user_login_token,
        first_account_with_all_affiliations,
        basic_ontology,
        basic_region,
        field_arrangement
):
    blocks_response = await post_to_blocks(client, first_user_login_token)
    blocks_payload = get_verified_payload(blocks_response, "blocks")
    assert blocks_payload.get('result')
    tree_unit_id = blocks_payload.get('result')[0].get('id')

    field_type_response = await post_to_get_entries(
        client, token=first_user_login_token,
        names=["field"], labels=[OntologyEntryLabel.LOCATION_TYPE]
    )
    field_type_payload = get_verified_payload(field_type_response, "ontologyEntries")
    field_type_id = field_type_payload.get('result')[0].get('id')

    field = next(basic_region.yield_locations_by_type(field_type_id))

    position = {
        'locationId': field.id,
        'layoutId': field_arrangement.root.id,
        'coordinates': ["1", "A"],
        'start': '2023'
    }
    add_position_response = await post_to_add_position(client, first_user_login_token, unit_id=tree_unit_id, position=position)
    add_position_payload = get_verified_payload(add_position_response, "blocksAddPosition")
    assert_payload_success(add_position_payload)