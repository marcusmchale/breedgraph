import pytest

from src.breedgraph.custom_exceptions import NoResultFoundError
from src.breedgraph.domain.model.ontology import OntologyEntryLabel

from tests.e2e.utils import get_verified_payload, assert_payload_success
from tests.e2e.regions.post_methods import post_to_countries, post_to_create_location, post_to_regions, post_to_location
from tests.e2e.ontologies.post_methods import post_to_get_entries

@pytest.mark.usefixtures("session_database")
@pytest.mark.asyncio(scope="session")
async def test_create_location(client, first_user_login_token, first_account_with_all_affiliations):
    countries_response = await post_to_countries(client, first_user_login_token)
    countries_payload = get_verified_payload(countries_response, "regionsCountries")
    assert countries_payload['result']
    country = countries_payload['result'][0]
    country['typeId'] = country.pop('type')['id']

    create_location_response = await post_to_create_location(
        client,
        token=first_user_login_token,
        location=country
    )
    create_location_payload = get_verified_payload(create_location_response, "regionsCreateLocation")
    assert_payload_success(create_location_payload)

    regions_request_response = await post_to_regions(client, first_user_login_token)
    regions_payload = get_verified_payload(regions_request_response, "regions")

    assert country.get('code') in [l.get('code') for l in regions_payload.get('result')]

@pytest.mark.asyncio(scope="session")
async def test_extend_region(client, basic_ontology, first_user_login_token, second_user_login_token):
    regions_request_response = await post_to_regions(client, first_user_login_token)
    regions_payload = get_verified_payload(regions_request_response, "regions")
    region_root_id = [l.get('id') for l in regions_payload.get('result')][0]

    state_type_response = await post_to_get_entries(client, token=first_user_login_token, names=["State"], labels=[OntologyEntryLabel.LOCATION_TYPE])
    state_type_payload = get_verified_payload(state_type_response, "ontologyEntries")
    state_type_id = state_type_payload.get('result')[0].get('id')

    new_name = 'New Territory'
    location = {
        'name': new_name,
        'typeId': state_type_id,
        'parentId': region_root_id,
    }
    create_response = await post_to_create_location(
        client,
        token=first_user_login_token,
        location=location
    )
    create_payload = get_verified_payload(create_response, "regionsCreateLocation")
    assert_payload_success(create_payload)

    regions_request_response = await post_to_regions(client, first_user_login_token)
    regions_payload = get_verified_payload(regions_request_response, "regions")

    for r in regions_payload.get('result'):
        if any([child.get('name')==new_name for child in r.get('children')]):
            child_id = [child.get('id') for child in r.get('children') if child.get('name') == new_name][0]
            break
    else:
        raise NoResultFoundError("Couldn't find the location in children")

    location_request_response = await post_to_location(client, location_id=child_id, token=first_user_login_token)
    location_payload = get_verified_payload(location_request_response, "regionsLocation")
    assert location_payload.get('result').get('parent').get('id') == region_root_id

    # assure this location isn't visible to a user without read affiliation.
    unaffililated_request_response = await post_to_location(client, location_id=region_root_id, token=second_user_login_token)
    unaffililated_payload = get_verified_payload(unaffililated_request_response, "regionsLocation")
    assert new_name not in [i.get('name') for i in unaffililated_payload.get('result').get('children')]
    # todo, reconsider access for non registered users, currently requiring authentication on most gql endpoints

