import pytest

from breedgraph.custom_exceptions import NoResultFoundError

from tests.breedgraph.e2e.utils import get_verified_payload, assert_payload_success
from tests.breedgraph.e2e.locations.post_methods import post_to_countries, post_to_create_location, post_to_locations_roots, post_to_locations


@pytest.mark.asyncio(loop_scope="session")
async def test_create_location(
        location_tree_build_context,
        login_token_factory,
        client
):
    user_id = location_tree_build_context['user_id']
    login_token = login_token_factory(user_id)
    countries_response = await post_to_countries(client, login_token)

    countries_payload = get_verified_payload(countries_response, "locationsCountries")
    assert countries_payload['result']

    country = countries_payload['result'][0]

    for country in countries_payload['result']:
        create_location_response = await post_to_create_location(
            client,
            token=login_token,
            location=country,
            control_team_id=location_tree_build_context['team_id']
        )
        create_location_payload = get_verified_payload(create_location_response, "locationsCreateLocation")
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

    location_trees_request_response = await post_to_locations_roots(client, login_token)
    location_trees_payload = get_verified_payload(location_trees_request_response, "locationsRoots")

    assert country.get('code') in [l.get('code') for l in location_trees_payload.get('result')]

@pytest.mark.asyncio(loop_scope="session")
async def test_create_country_once(
        location_tree_build_context,
        login_token_factory,
        client
):
    login_token = login_token_factory(location_tree_build_context['user_id'])
    countries = get_verified_payload(await post_to_countries(client, login_token), "locationsCountries")['result']
    location_trees = get_verified_payload(await post_to_locations_roots(client, login_token), "locationsRoots")['result']
    stored = {location_tree.get('code') for location_tree in location_trees}
    country = next(c for c in countries if c['code'] not in stored)

    async def create():
        response = await post_to_create_location(
            client, token=login_token, location=country, control_team_id=location_tree_build_context['team_id']
        )
        return get_verified_payload(response, "locationsCreateLocation")

    assert_payload_success(await create())
    # the countries read model was refreshed, so the country is known to be stored
    errors = (await create()).get('errors')
    assert errors and "already stored" in errors[0]['message']

@pytest.mark.asyncio(loop_scope="session")
async def test_extend_location_tree(
        location_tree_build_context,
        login_token_factory,
        client
):
    user_id = location_tree_build_context['user_id']
    login_token = login_token_factory(user_id)
    user_id_2 = location_tree_build_context['user_id_2']
    login_token_2 = login_token_factory(user_id_2)
    location_trees_request_response = await post_to_locations_roots(client, login_token)
    location_trees_payload = get_verified_payload(location_trees_request_response, "locationsRoots")
    location_tree_root_id = [l.get('id') for l in location_trees_payload.get('result')][0]

    state_type_id = location_tree_build_context['ontology_location_state']

    new_name = 'New Territory'
    location = {
        'name': new_name,
        'typeId': state_type_id,
        'parentId': location_tree_root_id,
    }
    create_response = await post_to_create_location(
        client,
        token=login_token,
        location=location,
        control_team_id=location_tree_build_context['team_id']
    )
    create_payload = get_verified_payload(create_response, "locationsCreateLocation")
    assert_payload_success(create_payload)

    location_trees_request_response = await post_to_locations_roots(client, login_token)
    location_trees_payload = get_verified_payload(location_trees_request_response, "locationsRoots")

    for r in location_trees_payload.get('result'):
        if any([child.get('name')==new_name for child in r.get('children')]):
            child_id = [child.get('id') for child in r.get('children') if child.get('name') == new_name][0]
            break
    else:
        raise NoResultFoundError("Couldn't find the location in children")

    location_request_response = await post_to_locations(client, location_ids=[child_id], token=login_token)
    location_payload = get_verified_payload(location_request_response, "locationsLocations")
    assert location_payload.get('result')[0].get('parent').get('id') == location_tree_root_id

    # assure this location isn't visible to a user without read affiliation.
    unaffililated_request_response = await post_to_locations(client, location_ids=[location_tree_root_id], token=login_token_2)
    unaffililated_payload = get_verified_payload(unaffililated_request_response, "locationsLocations")
    assert new_name not in [i.get('name') for i in unaffililated_payload.get('result')[0].get('children')]
    # todo, reconsider access for non registered users, currently requiring authentication on most gql endpoints

