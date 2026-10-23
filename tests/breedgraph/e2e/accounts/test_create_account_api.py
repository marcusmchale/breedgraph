import pytest

from breedgraph import config
from breedgraph.config import GQL_API_PATH
from breedgraph.service_layer.application.terms_of_use import load_legal_text

from tests.breedgraph.e2e.utils import get_verified_payload, assert_payload_success
from tests.breedgraph.utilities.inputs import UserInputGenerator


async def create_account(client, user_input, privacy_consent: bool):
    return await client.post(GQL_API_PATH, json={
        "query": (
            " mutation ( $name: String!, $email: String!, $password: String!, $consent: Boolean! ) { "
            "  accountsCreateAccount( name: $name, email: $email, password: $password, privacyConsent: $consent ) "
            "  { status, result, errors { name, message } } "
            " } "
        ),
        "variables": {
            "name": user_input['name'], "email": user_input['email'], "password": user_input['password'],
            "consent": privacy_consent
        }
    })


@pytest.mark.asyncio(loop_scope="session")
async def test_registering_needs_consent_to_the_privacy_notice(client, uow_factory, isolated_state):
    user_input = UserInputGenerator().new_user_input()
    payload = get_verified_payload(await create_account(client, user_input, privacy_consent=False), "accountsCreateAccount")
    assert payload['status'] == 'ERROR'
    assert "consent" in payload['errors'][0]['message']
    async with uow_factory.get_uow() as uow:
        assert await uow.repositories.accounts.get(name=user_input['name']) is None


@pytest.mark.asyncio(loop_scope="session")
async def test_create_account_without_fullname(client, uow_factory, isolated_state):
    user_input = UserInputGenerator().new_user_input()
    response = await create_account(client, user_input, privacy_consent=True)
    assert_payload_success(get_verified_payload(response, "accountsCreateAccount"))

    async with uow_factory.get_uow() as uow:
        account = await uow.repositories.accounts.get(name=user_input['name'])
    assert account.user.fullname == user_input['name']
    # the consent, recorded with the notice consented to
    assert account.user.privacy_consented_at is not None
    assert account.user.privacy_notice_hash == load_legal_text(config.PRIVACY_NOTICE_PATH).content_hash
