import pytest
import pytest_asyncio

from breedgraph import config
from breedgraph.domain.commands.organisations import DeclareLegalEntity, LegalEntity
from breedgraph.entrypoints.fastapi.graphql.decorators import GQLStatus

from tests.breedgraph.e2e.people.post_methods import (
    post_to_create_person, post_to_update_person, post_to_erase_person,
    post_to_people, post_to_people_by_ids, post_to_person
)
from tests.breedgraph.e2e.utils import get_verified_payload, assert_payload_success
from tests.breedgraph.scenarios.account_builder import AccountBuilder
from tests.breedgraph.scenarios.person_builder import PersonBuilder

TERMS_VERSION = 'test-terms-1'


@pytest.fixture(autouse=True)
def terms_version(monkeypatch):
    monkeypatch.setattr(config, 'DATA_PROCESSING_TERMS_VERSION', TERMS_VERSION)


@pytest_asyncio.fixture(scope="module", loop_scope="session")
async def people_api_context(isolated_state, uow_factory, bus) -> dict:
    account_builder = AccountBuilder(uow_factory)
    declared = await account_builder.account_with_affiliations()
    undeclared = await account_builder.account_with_affiliations()
    other_user_id = await account_builder.account()
    original = config.DATA_PROCESSING_TERMS_VERSION
    config.DATA_PROCESSING_TERMS_VERSION = TERMS_VERSION
    try:
        await bus.handle(DeclareLegalEntity(
            agent_id=declared['user_id'],
            team_id=declared['team_id'],
            legal_entity=LegalEntity(
                legal_name='Test University', privacy_contact='dataprotection@test.example', terms_version=TERMS_VERSION
            )
        ))
    finally:
        config.DATA_PROCESSING_TERMS_VERSION = original
    return {
        'user_id': declared['user_id'],
        'team_id': declared['team_id'],
        'undeclared_user_id': undeclared['user_id'],
        'undeclared_team_id': undeclared['team_id'],
        'other_user_id': other_user_id
    }


async def create_person(client, token, context) -> dict:
    name = PersonBuilder.person_input().name
    payload = get_verified_payload(await post_to_create_person(client, token, {
        'name': name,
        'teamIds': [context['team_id']],
        'informedAttestation': True
    }, context['team_id']), "peopleCreatePerson")
    assert_payload_success(payload)

    payload = get_verified_payload(await post_to_people(client, token, name), "people")
    assert_payload_success(payload)
    [person] = payload['result']
    return person


@pytest.mark.asyncio(loop_scope="session")
async def test_create_and_read(client, login_token_factory, people_api_context):
    token = login_token_factory(user_id=people_api_context['user_id'])
    person = await create_person(client, token, people_api_context)
    assert [team['id'] for team in person['teams']] == [str(people_api_context['team_id'])]
    assert person['basis'] == 'PUBLIC_TASK'
    assert person['informedAttestation'] is True
    assert person['recordedBy']['id'] == str(people_api_context['user_id'])
    assert person['recordedAt'] is not None
    assert person['restricted'] is False
    assert person['erased'] is False

    payload = get_verified_payload(await post_to_people(client, token), "people")
    assert person['id'] in [p['id'] for p in payload['result']]


@pytest.mark.asyncio(loop_scope="session")
async def test_other_users_see_id_only(client, login_token_factory, people_api_context):
    token = login_token_factory(user_id=people_api_context['user_id'])
    person = await create_person(client, token, people_api_context)

    other_token = login_token_factory(user_id=people_api_context['other_user_id'])
    payload = get_verified_payload(await post_to_person(client, other_token, int(person['id'])), "peoplePerson")
    assert_payload_success(payload)
    restricted = payload['result']
    assert restricted['id'] == person['id']
    assert restricted['restricted'] is True
    assert restricted['name'] is None
    assert restricted['teams'] == []
    assert restricted['recordedBy'] is None

    payload = get_verified_payload(await post_to_people_by_ids(client, other_token, [int(person['id'])]), "peoplePeople")
    assert [p['id'] for p in payload['result']] == [person['id']]

    # Not discoverable by name or in lists
    payload = get_verified_payload(await post_to_people(client, other_token, person['name']), "people")
    assert payload['result'] == []
    payload = get_verified_payload(await post_to_people(client, other_token), "people")
    assert person['id'] not in [p['id'] for p in payload['result']]


@pytest.mark.asyncio(loop_scope="session")
async def test_create_requires_legal_entity(client, login_token_factory, people_api_context):
    token = login_token_factory(user_id=people_api_context['undeclared_user_id'])
    payload = get_verified_payload(await post_to_create_person(client, token, {
        'name': 'A Technician', 'informedAttestation': True
    }, people_api_context['undeclared_team_id']), "peopleCreatePerson")
    assert payload['status'] == GQLStatus.ERROR.name
    assert 'legal entity' in payload['errors'][0]['message']


@pytest.mark.asyncio(loop_scope="session")
async def test_update_and_erase(client, login_token_factory, people_api_context):
    token = login_token_factory(user_id=people_api_context['user_id'])
    person = await create_person(client, token, people_api_context)
    person_id = int(person['id'])

    payload = get_verified_payload(await post_to_update_person(client, token, {
        'id': person_id, 'name': 'Renamed Person', 'teamIds': [], 'basis': 'LEGITIMATE_INTEREST'
    }), "peopleUpdatePerson")
    assert_payload_success(payload)
    updated = get_verified_payload(await post_to_person(client, token, person_id), "peoplePerson")['result']
    assert updated['name'] == 'Renamed Person'
    assert updated['teams'] == []
    assert updated['basis'] == 'LEGITIMATE_INTEREST'

    payload = get_verified_payload(await post_to_erase_person(client, token, person_id), "peopleErasePerson")
    assert_payload_success(payload)
    erased = get_verified_payload(await post_to_person(client, token, person_id), "peoplePerson")['result']
    assert erased['erased'] is True
    assert erased['erasedAt'] is not None
    assert erased['name'] is None
    assert erased['restricted'] is False
