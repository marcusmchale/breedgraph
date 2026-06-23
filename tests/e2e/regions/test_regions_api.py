import pytest

from src.breedgraph.custom_exceptions import NoResultFoundError

from tests.e2e.utils import get_verified_payload, assert_payload_success
from tests.e2e.regions.post_methods import post_to_countries, post_to_create_location, post_to_regions, post_to_locations
from tests.scenarios import reference_builder


@pytest.mark.asyncio(loop_scope="session")
async def test_create_location(
        region_build_context,
        login_token_factory,
        client
):
    user_id = region_build_context['user_id']
    login_token = login_token_factory(user_id)
    countries_response = await post_to_countries(client, login_token)

    countries_payload = get_verified_payload(countries_response, "regionsCountries")
    assert countries_payload['result']

    country = countries_payload['result'][0]

    for country in countries_payload['result']:
        create_location_response = await post_to_create_location(
            client,
            token=login_token,
            location=country
        )
        create_location_payload = get_verified_payload(create_location_response, "regionsCreateLocation")
        try:
            assert_payload_success(create_location_payload)
            break
        except AssertionError as e:
            payload_errors = create_location_payload.get('errors')
            exists_error = False
            for error in payload_errors:
                if error.get('name') == 'ValueError' and "already registered" in error.get('message'):
                    exists_error = True
            if not exists_error:
                raise ValueError(f"Unexpected error creating location: {e}")

    regions_request_response = await post_to_regions(client, login_token)
    regions_payload = get_verified_payload(regions_request_response, "regions")

    assert country.get('code') in [l.get('code') for l in regions_payload.get('result')]

@pytest.mark.asyncio(loop_scope="session")
async def test_extend_region(
        region_build_context,
        login_token_factory,
        client
):
    user_id = region_build_context['user_id']
    login_token = login_token_factory(user_id)
    user_id_2 = region_build_context['user_id_2']
    login_token_2 = login_token_factory(user_id_2)
    regions_request_response = await post_to_regions(client, login_token)
    regions_payload = get_verified_payload(regions_request_response, "regions")
    region_root_id = [l.get('id') for l in regions_payload.get('result')][0]

    state_type_id = region_build_context['ontology_location_state']

    new_name = 'New Territory'
    location = {
        'name': new_name,
        'typeId': state_type_id,
        'parentId': region_root_id,
    }
    create_response = await post_to_create_location(
        client,
        token=login_token,
        location=location
    )
    create_payload = get_verified_payload(create_response, "regionsCreateLocation")
    assert_payload_success(create_payload)

    regions_request_response = await post_to_regions(client, login_token)
    regions_payload = get_verified_payload(regions_request_response, "regions")

    for r in regions_payload.get('result'):
        if any([child.get('name')==new_name for child in r.get('children')]):
            child_id = [child.get('id') for child in r.get('children') if child.get('name') == new_name][0]
            break
    else:
        raise NoResultFoundError("Couldn't find the location in children")

    location_request_response = await post_to_locations(client, location_ids=[child_id], token=login_token)
    location_payload = get_verified_payload(location_request_response, "regionsLocations")
    assert location_payload.get('result')[0].get('parent').get('id') == region_root_id

    # assure this location isn't visible to a user without read affiliation.
    unaffililated_request_response = await post_to_locations(client, location_ids=[region_root_id], token=login_token_2)
    unaffililated_payload = get_verified_payload(unaffililated_request_response, "regionsLocations")
    assert new_name not in [i.get('name') for i in unaffililated_payload.get('result')[0].get('children')]
    # todo, reconsider access for non registered users, currently requiring authentication on most gql endpoints

