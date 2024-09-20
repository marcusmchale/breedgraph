import pytest
import pytest_asyncio

from tests.e2e.regions.post_methods import post_to_countries

from tests.e2e.payload_helpers import get_verified_payload


@pytest.mark.asyncio(scope="session")
async def test_create_region(client, first_user_login_token):
    response = await post_to_countries(client, first_user_login_token)
    payload = get_verified_payload(response, "countries")
    assert payload['result']

    country = payload['result'][0]


    # todo add new country and test is found

