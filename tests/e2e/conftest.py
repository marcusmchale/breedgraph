import pytest_asyncio

from accounts.post_methods import post_to_login
from accounts.test_registration_api import get_verified_payload, assert_payload_success


@pytest_asyncio.fixture(scope="session")
async def first_user_login_token(client, user_input_generator) -> str:
    first_user_input = user_input_generator.user_inputs[0]

    login_response = await post_to_login(
        client,
        first_user_input["name"],
        first_user_input["password"],
    )
    login_payload = get_verified_payload(login_response, "login")
    assert_payload_success(login_payload)
    yield login_payload['result']['access_token']

@pytest_asyncio.fixture(scope="session")
async def second_user_login_token(client, user_input_generator) -> str:
    second_user_input = user_input_generator.user_inputs[1]

    login_response = await post_to_login(
        client,
        second_user_input["name"],
        second_user_input["password"],
    )
    login_payload = get_verified_payload(login_response, "login")
    assert_payload_success(login_payload)
    yield login_payload['result']['access_token']