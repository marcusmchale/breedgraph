from urllib.parse import urlparse, parse_qs

import pytest
import pytest_asyncio

from breedgraph.entrypoints.fastapi.graphql.decorators import GQLStatus
from breedgraph.service_layer.handlers import handlers
from breedgraph.service_layer.infrastructure.orcid import AbstractOrcidService

from tests.breedgraph.e2e.people.post_methods import _post
from tests.breedgraph.e2e.utils import get_verified_payload, assert_payload_success
from tests.breedgraph.scenarios.account_builder import AccountBuilder
from tests.breedgraph.scenarios.person_builder import PersonBuilder


class FakeOrcidService(AbstractOrcidService):
    """Signs in whoever presents a code, as the ORCID iD the code names"""

    @property
    def configured(self) -> bool:
        return True

    def authorization_url(self, state: str) -> str:
        return f"https://sandbox.orcid.org/oauth/authorize?state={state}"

    async def verified_orcid(self, code: str) -> str:
        return code


@pytest.fixture(autouse=True)
def fake_orcid(monkeypatch):
    monkeypatch.setitem(handlers.dependencies, 'orcid_service', FakeOrcidService())


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


async def complete(client, token, code, state) -> dict:
    response = await _post(
        client, token,
        " mutation ( $code: String!, $state: String! ) { peopleCompleteOrcidLink( code: $code, state: $state ) "
        " { status, result, errors { name, message } } } ",
        {"code": code, "state": state}
    )
    return get_verified_payload(response, "peopleCompleteOrcidLink")


async def my_orcid(client, token):
    response = await _post(client, token, " query { peopleMyPerson { status, result { orcid }, errors { name, message } } } ")
    return get_verified_payload(response, "peopleMyPerson")['result']['orcid']


def state_from(payload) -> str:
    assert_payload_success(payload)
    return parse_qs(urlparse(payload['result']).query)['state'][0]


@pytest.mark.asyncio(loop_scope="session")
async def test_link_and_remove_orcid(client, login_token_factory, uow_factory, orcid_context):
    token = login_token_factory(user_id=await linked_user(uow_factory, orcid_context))
    state = state_from(await start(client, token))

    assert_payload_success(await complete(client, token, '0000-0002-1825-0097', state))
    assert await my_orcid(client, token) == '0000-0002-1825-0097'

    # Each state is used once
    payload = await complete(client, token, '0000-0002-1825-0097', state)
    assert payload['status'] == GQLStatus.ERROR.name

    response = await _post(client, token, " mutation { peopleRemoveOrcid { status, result, errors { name, message } } } ")
    assert_payload_success(get_verified_payload(response, "peopleRemoveOrcid"))
    assert await my_orcid(client, token) is None


@pytest.mark.asyncio(loop_scope="session")
async def test_state_belongs_to_the_user_who_started(client, login_token_factory, uow_factory, orcid_context):
    first_token = login_token_factory(user_id=await linked_user(uow_factory, orcid_context))
    second_token = login_token_factory(user_id=await linked_user(uow_factory, orcid_context))
    state = state_from(await start(client, first_token))

    payload = await complete(client, second_token, '0000-0002-1694-233X', state)
    assert payload['status'] == GQLStatus.ERROR.name
    assert await my_orcid(client, second_token) is None


@pytest.mark.asyncio(loop_scope="session")
async def test_orcid_linked_once(client, login_token_factory, uow_factory, orcid_context):
    first_token = login_token_factory(user_id=await linked_user(uow_factory, orcid_context))
    second_token = login_token_factory(user_id=await linked_user(uow_factory, orcid_context))
    orcid = '0000-0003-1415-9269'
    assert_payload_success(await complete(client, first_token, orcid, state_from(await start(client, first_token))))

    payload = await complete(client, second_token, orcid, state_from(await start(client, second_token)))
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
    payload = await complete(client, token, 'not-an-orcid', state_from(await start(client, token)))
    assert payload['status'] == GQLStatus.ERROR.name
