import pytest

from src.breedgraph.custom_exceptions import NoResultFoundError
from src.breedgraph.domain.model.ontology import OntologyEntryLabel
from tests.e2e.blocks.post_methods import post_to_create_unit, post_to_blocks, post_to_units, post_to_add_position
from tests.e2e.ontologies.post_methods import post_to_get_entries
from tests.e2e.utils import get_verified_payload, assert_payload_success

@pytest.mark.asyncio(loop_scope="session")
async def test_create_and_get(
        block_build_context,
        login_token_factory,
        client
):
    user_id = block_build_context['user_id']
    login_token = login_token_factory(user_id=user_id)
    location_id = block_build_context['location_id']
    subject_id = block_build_context['ontology_subject_tree']

    unit_input = {
        'subjectId': subject_id,
        'name': "New Tree",
    }
    initial_position = {
        'locationId': location_id
    }
    response = await post_to_create_unit(client, login_token, unit=unit_input, position=initial_position)
    payload = get_verified_payload(response, "blocksCreateUnit")
    assert_payload_success(payload)

    # get by first exploring the blocks at the location
    blocks_response = await post_to_blocks(client, login_token, location_ids=[location_id])
    blocks_payload = get_verified_payload(blocks_response, "blocks")
    assert blocks_payload.get('result')
    tree_unit_id = blocks_payload.get('result')[0].get('id')

    # validate get by unit ID also
    tree_unit_response = await post_to_units(client, unit_ids=[tree_unit_id], token=login_token)
    tree_unit_payload = get_verified_payload(tree_unit_response, "blocksUnits")
    assert tree_unit_payload.get('result')


@pytest.mark.asyncio(loop_scope="session")
async def test_extend_block(
        block_build_context,
        login_token_factory,
        client
):
    user_id = block_build_context['user_id']
    login_token = login_token_factory(user_id=user_id)
    location_id = block_build_context['location_id']
    rhizosphere_subject_id = block_build_context['ontology_subject_rhizosphere']
    field_subject_id = block_build_context['ontology_subject_field']

    field_unit_name = "Small Field"
    rhizosphere_unit_name = "New Tree Rhizosphere"
    # get an existing unit
    blocks_response = await post_to_blocks(client, login_token, location_ids=[location_id])
    blocks_payload = get_verified_payload(blocks_response, "blocks")
    assert blocks_payload.get('result')
    tree_unit_id = blocks_payload.get('result')[0].get('id')

    # create a new unit as a child
    rhizosphere_unit_input = {
        'subjectId': rhizosphere_subject_id,
        'name': rhizosphere_unit_name ,
        'parentIds':[tree_unit_id]
    }
    add_rhizosphere_response = await post_to_create_unit(client, login_token, unit=rhizosphere_unit_input)
    add_rhizosphere_payload = get_verified_payload(add_rhizosphere_response, "blocksCreateUnit")
    assert_payload_success(add_rhizosphere_payload)

    # create a new unit as a parent
    field_unit_input = {
        'subjectId': field_subject_id,
        'name': field_unit_name,
        'childrenIds': [tree_unit_id]
    }
    position = {
        'locationId': location_id
    }
    add_field_response = await post_to_create_unit(client, login_token, unit=field_unit_input, position=position)
    add_field_payload = get_verified_payload(add_field_response, "blocksCreateUnit")
    assert_payload_success(add_field_payload)

    # validate the block
    blocks_response = await post_to_blocks(client, login_token, location_ids=[location_id])
    blocks_payload = get_verified_payload(blocks_response, "blocks")
    assert blocks_payload.get('result')
    assert blocks_payload.get('result')[0].get('name') == field_unit_name
    assert blocks_payload.get('result')[0].get('children')[0].get('children')[0].get('name') == rhizosphere_unit_name


@pytest.mark.asyncio(loop_scope="session")
async def test_add_unit_position(
        block_build_context,
        login_token_factory,
        client
):
    user_id = block_build_context['user_id']
    login_token = login_token_factory(user_id=user_id)
    location_id = block_build_context['location_id']
    layout_id = block_build_context['layout_id']
    tree_type = block_build_context['ontology_subject_tree']

    blocks_response = await post_to_blocks(client, login_token, location_ids=[location_id])
    blocks_payload = get_verified_payload(blocks_response, "blocks")
    assert blocks_payload.get('result')
    tree_unit = blocks_payload.get('result')[0]
    limit = 10
    while True:
        limit -= 1
        if limit == 0:
            raise NoResultFoundError("Could not find tree unit in block at location")
        if tree_unit.get('subject').get('id') == tree_type:
            break
        else:
            tree_unit = tree_unit.get('children')[0]

    tree_unit_id = tree_unit.get('id')

    position = {
        'locationId': location_id,
        'layoutId': layout_id,
        'coordinates': ["1", "1"],
        'start': '2023'
    }
    add_position_response = await post_to_add_position(client, login_token, unit_id=tree_unit_id, position=position)
    add_position_payload = get_verified_payload(add_position_response, "blocksAddPosition")
    assert_payload_success(add_position_payload)