import pytest

from breedgraph import config
from breedgraph.config import GQL_API_PATH, SITE_NAME
from breedgraph.service_layer.application.terms_of_use import load_legal_text

from tests.breedgraph.e2e.accounts.post_methods import post_to_invite
from tests.breedgraph.e2e.utils import get_verified_payload, assert_payload_success
from tests.breedgraph.scenarios.account_builder import AccountBuilder
from tests.breedgraph.utilities.inputs import UserInputGenerator
from tests.breedgraph.utilities.mailhog_fetching import get_json_from_email


async def create_account(client, user_input, privacy_consent: bool, invitation_token: str | None = None):
    return await client.post(GQL_API_PATH, json={
        "query": (
            " mutation ( $name: String!, $email: String!, $password: String!, $consent: Boolean!, $token: String ) { "
            "  accountsCreateAccount( "
            "   name: $name, email: $email, password: $password, privacyConsent: $consent, invitationToken: $token "
            "  ) { status, result, errors { name, message } } "
            " } "
        ),
        "variables": {
            "name": user_input['name'], "email": user_input['email'], "password": user_input['password'],
            "consent": privacy_consent, "token": invitation_token
        }
    })


async def invitation_token(client, uow_factory, login_token_factory, email: str) -> str:
    """The token of an invitation to the address, sent by an account of its own"""
    inviter = login_token_factory(await AccountBuilder(uow_factory).account())
    assert_payload_success(get_verified_payload(await post_to_invite(client, inviter, email), "accountsInvite"))
    return (await get_json_from_email(mailto=email, subject=f"Invitation to register with {SITE_NAME}"))['token']


@pytest.mark.asyncio(loop_scope="session")
async def test_registering_needs_consent_to_the_privacy_notice(client, uow_factory, isolated_state):
    user_input = UserInputGenerator().new_user_input()
    payload = get_verified_payload(await create_account(client, user_input, privacy_consent=False), "accountsCreateAccount")
    assert payload['status'] == 'ERROR'
    assert "consent" in payload['errors'][0]['message']
    async with uow_factory.get_uow() as uow:
        assert await uow.repositories.accounts.get(name=user_input['name']) is None


@pytest.mark.asyncio(loop_scope="session")
async def test_registering_needs_an_invitation_even_on_a_new_site(client, uow_factory, isolated_state):
    # the database is empty, as a new site's is before scripts/create_first_account.py
    async with uow_factory.get_uow() as uow:
        assert not await uow.constraints.accounts_exist()
    user_input = UserInputGenerator().new_user_input()
    payload = get_verified_payload(await create_account(client, user_input, privacy_consent=True), "accountsCreateAccount")
    assert payload['status'] == 'ERROR'
    assert payload['errors'][0]['message'] == "Please contact an existing user to be invited"
    async with uow_factory.get_uow() as uow:
        assert await uow.repositories.accounts.get(name=user_input['name']) is None


@pytest.mark.asyncio(loop_scope="session")
async def test_create_account_without_fullname(client, uow_factory, login_token_factory, isolated_state):
    user_input = UserInputGenerator().new_user_input()
    token = await invitation_token(client, uow_factory, login_token_factory, user_input['email'])
    response = await create_account(client, user_input, privacy_consent=True, invitation_token=token)
    assert_payload_success(get_verified_payload(response, "accountsCreateAccount"))

    async with uow_factory.get_uow() as uow:
        account = await uow.repositories.accounts.get(name=user_input['name'])
    assert account.user.fullname == user_input['name']
    assert account.user.ontology_role.name == 'CONTRIBUTOR'
    # the consent, recorded with the notice consented to
    assert account.user.privacy_consented_at is not None
    assert account.user.privacy_notice_hash == load_legal_text(config.PRIVACY_NOTICE_PATH).content_hash
