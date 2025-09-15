import pytest

from src.breedgraph.custom_exceptions import NoResultFoundError

from tests.e2e.utils import get_verified_payload, assert_payload_success
from tests.e2e.regions.post_methods import post_to_countries, post_to_add_location, post_to_regions, post_to_location

@pytest.mark.usefixtures("session_database")
@pytest.mark.asyncio(scope="session")
async def test_create_location(client, first_user_login_token, first_account_with_all_affiliations):
    countries_response = await post_to_countries(client, first_user_login_token)
    countries_payload = get_verified_payload(countries_response, "countries")
    assert countries_payload['result']
    country = countries_payload['result'][0]
    country['type'] = country['type']['id']
    await post_to_add_location(
        client,
        token=first_user_login_token,
        location=country
    )
    regions_request_response = await post_to_regions(client, first_user_login_token)
    regions_payload = get_verified_payload(regions_request_response, "regions")
    assert country.get('code') in [l.get('code') for l in regions_payload.get('result')]

@pytest.mark.asyncio(scope="session")
async def test_extend_region(client, first_user_login_token, basic_ontology_service):
    regions_request_response = await post_to_regions(client, first_user_login_token)
    regions_payload = get_verified_payload(regions_request_response, "regions")
    region_root_id = [l.get('id') for l in regions_payload.get('result')][0]
    state_type_id, state_type = basic_ontology_service.get_entry("State", label="LocationType")

    new_name = 'New Territory'
    location = {
        'name': new_name,
        'type': state_type_id,
        'parent': region_root_id,
        'release': "REGISTERED"
    }
    await post_to_add_location(
        client,
        token=first_user_login_token,
        location=location
    )
    regions_request_response = await post_to_regions(client, first_user_login_token)
    regions_payload = get_verified_payload(regions_request_response, "regions")

    for r in regions_payload.get('result'):
        if any([child.get('name')==new_name for child in r.get('children')]):
            child_id = [child.get('id') for child in r.get('children') if child.get('name') == new_name][0]
            break
    else:
        raise NoResultFoundError("Couldn't find the location in children")


    location_request_response = await post_to_location(client, location_id=child_id, token=first_user_login_token)
    location_payload = get_verified_payload(location_request_response, "location")
    assert location_payload.get('result').get('parent').get('id') == region_root_id

    # todo, reconsider access for non registered users, currently requiring authentication on most gql endpoints
    # we could modify this to
    ## assure is not visible to unregistered when query region
    #unregistered_region_request_response = await post_to_location(client, location_id=region_root_id)
    #import pdb;
    #pdb.set_trace()
    #unregistered_region_payload = get_verified_payload(unregistered_region_request_response, "location")
    #assert not new_name in [i.get('name') for i in unregistered_region_payload.get('result').get('children')]


    ## assure is not visible to unregistered when query location
    #unregistered_location_request_response = await post_to_location(client, location_id=child_id)
    #unregistered_location_payload = get_verified_payload(unregistered_location_request_response, "location")
    #assert unregistered_location_payload.get('result') is None

@pytest.mark.asyncio(scope="session")
async def test_extend_with_private_field(client, first_user_login_token, second_user_login_token,
                                         basic_ontology_service):
    regions_request_response = await post_to_regions(client, first_user_login_token)
    regions_payload = get_verified_payload(regions_request_response, "regions")
    region_root_id = [l.get('id') for l in regions_payload.get('result')][0]
    state_id = [l.get('children')[0].get('id') for l in regions_payload.get('result') if l.get('children')][0]
    field_type_id, field_type = basic_ontology_service.get_entry("Field", label="LocationType")
    new_name = 'Private Field'
    location = {
        'name': new_name,
        'type': field_type_id,
        'parent': state_id,
        'release': "PRIVATE"
    }
    add_location_response = await post_to_add_location(
        client,
        token=first_user_login_token,
        location=location
    )
    add_location_payload = get_verified_payload(add_location_response, "add_location")
    assert_payload_success(add_location_payload)

    state_request_response = await post_to_location(client, location_id=state_id, token=first_user_login_token)
    state_payload = get_verified_payload(state_request_response, "location")
    assert state_payload.get('result').get('parent').get('id') == region_root_id
    assert new_name in [i.get('name') for i in state_payload.get('result').get('children')]

    # assure this new field isn't visible to a user without read affiliation.
    unaffililated_state_request_response = await post_to_location(client, location_id=state_id, token=second_user_login_token)
    unaffililated_state_payload = get_verified_payload(unaffililated_state_request_response, "location")
    assert unaffililated_state_payload.get('result').get('parent').get('id') == region_root_id
    assert new_name not in [i.get('name') for i in unaffililated_state_payload.get('result').get('children')]

