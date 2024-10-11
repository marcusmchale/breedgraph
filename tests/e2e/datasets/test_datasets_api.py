import pytest

from tests.e2e.datasets.post_methods import post_to_add_dataset
from tests.e2e.ontologies.post_methods import post_to_get_entries
from tests.e2e.payload_helpers import get_verified_payload

@pytest.mark.usefixtures("session_database")
@pytest.mark.asyncio(scope="session")
async def test_create_dataset(
        client,
        first_user_login_token,
        first_account_with_all_affiliations,
        basic_ontology
):
    variable_response = await post_to_get_entries(
        client,
        token=first_user_login_token,
        label="Variable"
    )
    variable_payload = get_verified_payload(variable_response, "ontology_entries")
    variable_id = variable_payload.get('result')[0].get('id')
    response = await post_to_add_dataset(client, first_user_login_token, term=variable_id)
    payload = get_verified_payload(response, "data_add_dataset")
    assert payload['result']

@pytest.mark.asyncio(scope="session")
async def test_extend_dataset(
        client,
        first_user_login_token,
        first_account_with_all_affiliations,
        basic_ontology
):
    datasets_response = await post_to_get_datasets(
        client,
        token=first_user_login_token
    )
