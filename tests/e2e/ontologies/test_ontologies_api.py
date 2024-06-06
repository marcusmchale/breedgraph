import pytest

from tests.e2e.payload_helpers import get_verified_payload
from tests.e2e.ontologies.post_methods import post_to_add_term
from tests.e2e.accounts.test_registration_api import assert_payload_success

@pytest.mark.usefixtures("session_database")
@pytest.mark.asyncio(scope="session")
async def test_add_term(client, second_user_login_token, lorem_text_generator):
    response = await post_to_add_term(
        client,
        token=second_user_login_token,
        name=lorem_text_generator.new_text(10),
        description=lorem_text_generator.new_text(20),
        abbreviation=lorem_text_generator.new_text(5),
        synonyms=[lorem_text_generator.new_text(10),lorem_text_generator.new_text(5)]
    )
    assert_payload_success(get_verified_payload(response, "add_term"))


