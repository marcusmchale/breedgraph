from urllib.parse import urlparse, parse_qs

import pytest
import pytest_asyncio

from breedgraph import config
from breedgraph.adapters.orcid import OidcOrcidService
from breedgraph.entrypoints.fastapi.graphql.decorators import GQLStatus
from breedgraph.service_layer.handlers import handlers

from tests.breedgraph.e2e.people.post_methods import _post
from tests.breedgraph.e2e.utils import get_verified_payload, assert_payload_success
from tests.breedgraph.scenarios.account_builder import AccountBuilder
from tests.breedgraph.scenarios.person_builder import PersonBuilder
from tests.breedgraph.utilities.orcid_tokens import configure_orcid, id_token


@pytest.fixture(autouse=True)
def orcid(monkeypatch, tmp_path):
    """ORCID sign-in as configured, with a key made for the tests held as ORCID's, so ORCID is not contacted"""
    configure_orcid(monkeypatch, tmp_path)
    monkeypatch.setitem(handlers.dependencies, 'orcid_service', OidcOrcidService())


@pytest_asyncio.fixture(scope="module", loop_scope="session")
async def orcid_context(isolated_state, uow_factory) -> dict:
    admin = await AccountBuilder(uow_factory).account_with_affiliations()
    return {'user_id': admin['user_id'], 'team_id': admin['team_id']}


async def linked_user(uow_factory, context) -> int:
    user_id = await AccountBuilder(uow_factory).account()
    person_id = await PersonBuilder(uow_factory).person(user_id=context['user_id'], team_id=context['team_id'])
    async with uow_factory.get_uow(user_id=context['user_id']) as uow:
        person = await uow.repositories.people.get(person_id=person_id)
        person.link(user_id)
        await uow.commit()
    return user_id


async def start(client, token) -> dict:
    response = await _post(client, token, " mutation { peopleStartOrcidLink { status, result, errors { name, message } } } ")
    return get_verified_payload(response, "peopleStartOrcidLink")


async def sign_in(client, token) -> tuple[str, str]:
    """The state of a sign-in started, and the nonce ORCID is asked to put in the id_token"""
    payload = await start(client, token)
    assert_payload_success(payload)
    query = parse_qs(urlparse(payload['result']).query)
    return query['state'][0], query['nonce'][0]


async def complete(client, token, id_token, state) -> dict:
    response = await _post(
        client, token,
        " mutation ( $idToken: String!, $state: String! ) { peopleCompleteOrcidLink( idToken: $idToken, state: $state ) "
        " { status, result, errors { name, message } } } ",
        {"idToken": id_token, "state": state}
    )
    return get_verified_payload(response, "peopleCompleteOrcidLink")


async def my_orcid(client, token):
    response = await _post(client, token, " query { peopleMyPerson { status, result { orcid }, errors { name, message } } } ")
    return get_verified_payload(response, "peopleMyPerson")['result']['orcid']


@pytest.mark.asyncio(loop_scope="session")
async def test_link_and_remove_orcid(client, login_token_factory, uow_factory, orcid_context):
    token = login_token_factory(user_id=await linked_user(uow_factory, orcid_context))
    state, nonce = await sign_in(client, token)

    assert_payload_success(await complete(client, token, id_token(nonce, sub='0000-0002-1825-0097'), state))
    assert await my_orcid(client, token) == '0000-0002-1825-0097'

    # Each state is used once
    payload = await complete(client, token, id_token(nonce, sub='0000-0002-1825-0097'), state)
    assert payload['status'] == GQLStatus.ERROR.name

    response = await _post(client, token, " mutation { peopleRemoveOrcid { status, result, errors { name, message } } } ")
    assert_payload_success(get_verified_payload(response, "peopleRemoveOrcid"))
    assert await my_orcid(client, token) is None


@pytest.mark.asyncio(loop_scope="session")
async def test_state_belongs_to_the_user_who_started(client, login_token_factory, uow_factory, orcid_context):
    first_token = login_token_factory(user_id=await linked_user(uow_factory, orcid_context))
    second_token = login_token_factory(user_id=await linked_user(uow_factory, orcid_context))
    state, nonce = await sign_in(client, first_token)

    payload = await complete(client, second_token, id_token(nonce, sub='0000-0002-1694-233X'), state)
    assert payload['status'] == GQLStatus.ERROR.name
    assert await my_orcid(client, second_token) is None


@pytest.mark.asyncio(loop_scope="session")
async def test_id_token_must_hold_the_nonce_of_the_state(client, login_token_factory, uow_factory, orcid_context):
    """An id_token ORCID gave someone else, or for another sign-in, does not link its iD"""
    first_token = login_token_factory(user_id=await linked_user(uow_factory, orcid_context))
    second_token = login_token_factory(user_id=await linked_user(uow_factory, orcid_context))
    _, first_nonce = await sign_in(client, first_token)
    second_state, _ = await sign_in(client, second_token)

    payload = await complete(client, second_token, id_token(first_nonce, sub='0000-0001-5109-3700'), second_state)
    assert payload['status'] == GQLStatus.ERROR.name
    assert 'could not be verified' in payload['errors'][0]['message']
    assert await my_orcid(client, second_token) is None


@pytest.mark.asyncio(loop_scope="session")
async def test_orcid_linked_once(client, login_token_factory, uow_factory, orcid_context):
    first_token = login_token_factory(user_id=await linked_user(uow_factory, orcid_context))
    second_token = login_token_factory(user_id=await linked_user(uow_factory, orcid_context))
    orcid = '0000-0003-1415-9269'
    state, nonce = await sign_in(client, first_token)
    assert_payload_success(await complete(client, first_token, id_token(nonce, sub=orcid), state))

    state, nonce = await sign_in(client, second_token)
    payload = await complete(client, second_token, id_token(nonce, sub=orcid), state)
    assert payload['status'] == GQLStatus.ERROR.name
    assert 'already linked' in payload['errors'][0]['message']


@pytest.mark.asyncio(loop_scope="session")
async def test_requires_linked_person(client, login_token_factory, uow_factory, orcid_context):
    token = login_token_factory(user_id=await AccountBuilder(uow_factory).account())
    payload = await start(client, token)
    assert payload['status'] == GQLStatus.ERROR.name
    assert 'not linked to a Person' in payload['errors'][0]['message']


@pytest.mark.asyncio(loop_scope="session")
async def test_invalid_orcid_refused(client, login_token_factory, uow_factory, orcid_context):
    token = login_token_factory(user_id=await linked_user(uow_factory, orcid_context))
    state, nonce = await sign_in(client, token)
    payload = await complete(client, token, id_token(nonce, sub='not-an-orcid'), state)
    assert payload['status'] == GQLStatus.ERROR.name


@pytest.mark.asyncio(loop_scope="session")
async def test_the_profile_is_told_whether_an_orcid_id_can_be_linked(client, login_token_factory, uow_factory, bus, monkeypatch):
    """Only where the site has an ORCID client: not on the demonstration site, whose ORCID would send people elsewhere"""
    token = login_token_factory(await AccountBuilder(uow_factory).account())
    query = " query { peopleOrcidLinking { status, result, errors { name, message } } } "
    monkeypatch.setattr(bus, 'orcid_service', OidcOrcidService())
    assert get_verified_payload(await _post(client, token, query), "peopleOrcidLinking")['result'] is True
    monkeypatch.setattr(config, 'ORCID_CLIENT_ID', None)
    assert get_verified_payload(await _post(client, token, query), "peopleOrcidLinking")['result'] is False
