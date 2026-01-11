import pytest, pytest_asyncio

from tests.e2e.controls.post_methods import post_to_set_release, post_to_controllers
from tests.e2e.regions.post_methods import post_to_create_location, post_to_locations
from tests.e2e.ontologies.post_methods import post_to_get_entries

from src.breedgraph.domain.model.ontology import OntologyEntryLabel
from src.breedgraph.domain.model.controls import ControlledModelLabel, ReadRelease

from tests.e2e.utils import get_verified_payload, assert_payload_success

@pytest_asyncio.fixture(scope="session")
async def new_location_id(
        client,
        basic_ontology,
        basic_region,
        first_user_login_token,
        first_account_with_all_affiliations
):
    state_type_response = await post_to_get_entries(client, token=first_user_login_token, names=["State"],
                                                    labels=[OntologyEntryLabel.LOCATION_TYPE])
    state_type_payload = get_verified_payload(state_type_response, "ontologyEntries")
    state_type_id = state_type_payload.get('result')[0].get('id')
    new_name = 'New Territory Control Testing'
    location = {
        'name': new_name,
        'typeId': state_type_id,
        'parentId': basic_region.get_root_id(),
    }
    response = await post_to_create_location(client, first_user_login_token, location=location)
    payload = get_verified_payload(response, "regionsCreateLocation")
    assert payload['result']

    region_response = await post_to_locations(client, location_ids=[basic_region.get_root_id()],
                                              token=first_user_login_token)
    region_payload = get_verified_payload(region_response, "regionsLocations")
    assert region_payload['result']
    location = [l for l in region_payload['result'][0].get('children') if l.get('name') == new_name][0]
    yield location.get('id')


@pytest.mark.usefixtures("session_database")
@pytest.mark.asyncio(scope="session")
async def test_get_controls(
        client,
        first_user_login_token,
        new_location_id
):
    controllers_response = await post_to_controllers(
        client=client,
        token=first_user_login_token,
        entity_label=ControlledModelLabel.LOCATION,
        entity_ids = [new_location_id]
    )
    controllers_payload = get_verified_payload(controllers_response, "controlsControllers")
    assert_payload_success(controllers_payload)
    assert(controllers_payload.get('result')[0].get('release') == 'PRIVATE')


@pytest.mark.usefixtures("session_database")
@pytest.mark.asyncio(scope="session")
async def test_set_controls(
        client,
        first_user_login_token,
        new_location_id
):
    controllers_response = await post_to_controllers(
        client=client,
        token=first_user_login_token,
        entity_label=ControlledModelLabel.LOCATION,
        entity_ids=[new_location_id]
    )
    controllers_payload = get_verified_payload(controllers_response, "controlsControllers")
    assert_payload_success(controllers_payload)
    assert (controllers_payload.get('result')[0].get('release') == 'PRIVATE')

    set_controls_response = await post_to_set_release(
        client=client,
        token=first_user_login_token,
        entity_label=ControlledModelLabel.LOCATION,
        entity_ids=[new_location_id],
        release=ReadRelease.PUBLIC
    )
    set_controls_payload = get_verified_payload(set_controls_response, "controlsSetRelease")
    assert_payload_success(set_controls_payload)

    controllers_response2 = await post_to_controllers(
        client=client,
        token=first_user_login_token,
        entity_label=ControlledModelLabel.LOCATION,
        entity_ids=[new_location_id]
    )
    controllers_payload2 = get_verified_payload(controllers_response2, "controlsControllers")
    assert_payload_success(controllers_payload2)
    assert (controllers_payload2.get('result')[0].get('release') == 'PUBLIC')