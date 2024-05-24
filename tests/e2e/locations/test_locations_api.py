import pytest
import pytest_asyncio

from tests.e2e.locations.post_methods import post_to_countries

from tests.e2e.payload_helpers import get_verified_payload

#@pytest.mark.usefixtures("session_database")
#@pytest.mark.asyncio(scope="session")
#async def test_get_countries_add_new(client, admin_login_token):
#    response = await post_to_countries(client, admin_login_token)
#    payload = get_verified_payload(response, "countries")
#    assert payload['result']
#    # todo add new country and test is found

