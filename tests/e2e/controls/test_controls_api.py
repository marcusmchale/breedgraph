import pytest

from tests.e2e.controls.post_methods import post_to_set_controls, post_to_controllers
from tests.e2e.datasets.post_methods import post_to_create_dataset
from tests.e2e.ontologies.post_methods import post_to_get_entries

from src.breedgraph.domain.model.ontology import OntologyEntryLabel
from src.breedgraph.domain.model.controls import ControlledModelLabel, ReadRelease

from tests.e2e.utils import get_verified_payload, assert_payload_success


@pytest.mark.usefixtures("session_database")
@pytest.mark.asyncio(scope="session")
async def test_get_controls(
        client,
        first_user_login_token,
        first_account_with_all_affiliations,
        basic_ontology
):
    # first just make sure a dataset exists
    variable_response = await post_to_get_entries(
        client,
        token=first_user_login_token,
        labels=[OntologyEntryLabel.VARIABLE]
    )
    variable_payload = get_verified_payload(variable_response, "ontologyEntries")
    variable_id = variable_payload.get('result')[0].get('id')
    response = await post_to_create_dataset(client, first_user_login_token, concept_id=variable_id)
    payload = get_verified_payload(response, "datasetsCreateDataset")
    assert payload['result']
    controllers_response = await post_to_controllers(
        client=client,
        token=first_user_login_token,
        entity_label=ControlledModelLabel.DATASET,
        entity_ids = [1]
    )
    controllers_payload = get_verified_payload(controllers_response, "controlsControllers")
    assert_payload_success(controllers_payload)
    assert(controllers_payload.get('result')[0].get('release') == 'PRIVATE')


@pytest.mark.usefixtures("session_database")
@pytest.mark.asyncio(scope="session")
async def test_set_controls(
        client,
        first_user_login_token,
        first_account_with_all_affiliations,
        basic_ontology
):
    controllers_response = await post_to_controllers(
        client=client,
        token=first_user_login_token,
        entity_label=ControlledModelLabel.DATASET,
        entity_ids=[1]
    )
    controllers_payload = get_verified_payload(controllers_response, "controlsControllers")
    assert_payload_success(controllers_payload)
    assert (controllers_payload.get('result')[0].get('release') == 'PRIVATE')

    set_controls_response = await post_to_set_controls(
        client=client,
        token=first_user_login_token,
        entity_label=ControlledModelLabel.DATASET,
        entity_ids=[1],
        release=ReadRelease.PUBLIC
    )
    set_controls_payload = get_verified_payload(set_controls_response, "controlsSetControls")
    assert_payload_success(set_controls_payload)

    controllers_response = await post_to_controllers(
        client=client,
        token=first_user_login_token,
        entity_label=ControlledModelLabel.DATASET,
        entity_ids=[1]
    )
    controllers_payload = get_verified_payload(controllers_response, "controlsControllers")
    assert_payload_success(controllers_payload)
    assert (controllers_payload.get('result')[0].get('release') == 'PUBLIC')