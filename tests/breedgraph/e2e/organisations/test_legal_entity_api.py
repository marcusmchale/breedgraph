import pytest

from breedgraph import config
from breedgraph.entrypoints.fastapi.graphql.decorators import GQLStatus

from tests.breedgraph.e2e.organisations.post_methods import (
    post_to_create_team, post_to_organisations, post_to_data_processing_terms,
    post_to_declare_legal_entity, post_to_team_legal_entity
)
from tests.breedgraph.e2e.utils import get_verified_payload, assert_payload_success
from tests.breedgraph.scenarios.account_builder import AccountBuilder
from tests.breedgraph.scenarios.organisation_builder import OrganisationBuilder


@pytest.fixture
def terms(monkeypatch) -> dict:
    monkeypatch.setattr(config, 'DATA_PROCESSING_TERMS_VERSION', 'test-terms-1')
    monkeypatch.setattr(config, 'DATA_PROCESSING_TERMS_URL', 'https://terms.test.example/v1')
    return {'version': 'test-terms-1', 'url': 'https://terms.test.example/v1'}


def legal_entity_input(terms_version: str) -> dict:
    return {
        'legalName': 'Test University',
        'privacyContact': 'dataprotection@test.example',
        'termsVersion': terms_version
    }


@pytest.mark.asyncio(loop_scope="session")
async def test_data_processing_terms(client, terms):
    payload = get_verified_payload(await post_to_data_processing_terms(client), "organisationsDataProcessingTerms")
    assert_payload_success(payload)
    assert payload['result'] == terms


@pytest.mark.asyncio(loop_scope="session")
async def test_create_organisation_with_legal_entity(client, login_token_factory, uow_factory, isolated_state, terms):
    user_id = await AccountBuilder(uow_factory).account()
    token = login_token_factory(user_id=user_id)
    name = OrganisationBuilder.team_input().name
    payload = get_verified_payload(
        await post_to_create_team(client, token, {'name': name, 'legalEntity': legal_entity_input(terms['version'])}),
        "organisationsCreateTeam"
    )
    assert_payload_success(payload)

    payload = get_verified_payload(await post_to_organisations(client, token), "organisations")
    [team_id] = [int(team['id']) for team in payload['result'] if team['name'] == name]
    payload = get_verified_payload(await post_to_team_legal_entity(client, token, team_id), "organisationsTeam")
    assert_payload_success(payload)
    legal_entity = payload['result']['legalEntity']
    assert legal_entity['legalName'] == 'Test University'
    assert legal_entity['privacyContact'] == 'dataprotection@test.example'
    assert legal_entity['termsVersion'] == terms['version']
    assert legal_entity['declaredAt'] is not None
    assert int(legal_entity['declaredBy']['id']) == user_id


@pytest.mark.asyncio(loop_scope="session")
async def test_declare_legal_entity(client, login_token_factory, uow_factory, isolated_state, terms):
    account = await AccountBuilder(uow_factory).account_with_affiliations()
    other_user_id = await AccountBuilder(uow_factory).account()
    token = login_token_factory(user_id=account['user_id'])
    other_token = login_token_factory(user_id=other_user_id)

    # Only root admins can declare, and only with the current terms
    payload = get_verified_payload(
        await post_to_declare_legal_entity(client, other_token, account['team_id'], legal_entity_input(terms['version'])),
        "organisationsDeclareLegalEntity"
    )
    assert payload['status'] == GQLStatus.ERROR.name
    payload = get_verified_payload(
        await post_to_declare_legal_entity(client, token, account['team_id'], legal_entity_input('old-terms')),
        "organisationsDeclareLegalEntity"
    )
    assert payload['status'] == GQLStatus.ERROR.name

    payload = get_verified_payload(
        await post_to_declare_legal_entity(client, token, account['team_id'], legal_entity_input(terms['version'])),
        "organisationsDeclareLegalEntity"
    )
    assert_payload_success(payload)

    # Other users see the legal entity, but not who declared it
    payload = get_verified_payload(await post_to_team_legal_entity(client, other_token, account['team_id']), "organisationsTeam")
    assert_payload_success(payload)
    legal_entity = payload['result']['legalEntity']
    assert legal_entity['legalName'] == 'Test University'
    assert legal_entity['declaredBy'] is None
