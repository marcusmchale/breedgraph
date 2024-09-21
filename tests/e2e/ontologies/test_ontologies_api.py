import pytest

from tests.e2e.payload_helpers import get_verified_payload
from tests.e2e.ontologies.post_methods import post_to_add_entry, post_to_get_entries
from tests.e2e.accounts.test_registration_api import assert_payload_success

@pytest.mark.usefixtures("session_database")
@pytest.mark.asyncio(scope="session")
async def test_add_term(client, second_user_login_token, lorem_text_generator):
    response = await post_to_add_entry(
        client,
        token=second_user_login_token,
        label="Term",
        name=lorem_text_generator.new_text(10),
        description=lorem_text_generator.new_text(20),
        abbreviation=lorem_text_generator.new_text(5),
        synonyms=[lorem_text_generator.new_text(10),lorem_text_generator.new_text(5)]
    )
    assert_payload_success(get_verified_payload(response, "ontology_add_entry"))

@pytest.mark.usefixtures("session_database")
@pytest.mark.asyncio(scope="session")
async def test_add_subject(client, second_user_login_token, lorem_text_generator):
    response = await post_to_get_entries(client, token=second_user_login_token, label="Term")
    term_payload = get_verified_payload(response, "ontology_entries")
    term_id = term_payload.get('result')[0].get('id')
    response = await post_to_add_entry(
        client,
        token=second_user_login_token,
        label="Subject",
        name=lorem_text_generator.new_text(10),
        description=lorem_text_generator.new_text(20),
        abbreviation=lorem_text_generator.new_text(5),
        synonyms=[lorem_text_generator.new_text(10),lorem_text_generator.new_text(5)],
        parents=[term_id],
    )
    assert_payload_success(get_verified_payload(response, "ontology_add_entry"))
    response = await post_to_get_entries(client, token=second_user_login_token, label="Subject")
    subject_payload = get_verified_payload(response, "ontology_entries")
    assert subject_payload.get('result')[0].get('id')
    assert term_id in [i.get('id') for i in subject_payload.get('result')[0].get('parents')]

#@pytest.mark.usefixtures("session_database")
#@pytest.mark.asyncio(scope="session")
#async def test_add_trait(client, second_user_login_token, lorem_text_generator):
#    response = await post_to_get_entries(
#        client,
#        token=second_user_login_token,
#        label="Subject"
#    )
#    import pdb; pdb.set_trace()
#    assert_payload_success(get_verified_payload(response, "ontology_entries"))