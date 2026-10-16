import pytest
import pytest_asyncio

from breedgraph.domain.model import Access
from breedgraph.domain.model.accounts import UserInput, AccountInput, OntologyRole
from breedgraph.domain.model.controls import ControlledModelLabel
from breedgraph.entrypoints.fastapi.graphql.decorators import GQLStatus
from breedgraph.adapters.files import JsonLinesErasureLog
from breedgraph.adapters.neo4j.erasures import apply_erasures
from breedgraph.service_layer.infrastructure.erasure_log import AccountDeletionLogEntry, ErasureLogEntry

from tests.breedgraph.e2e.accounts.post_methods import _post
from tests.breedgraph.e2e.people.post_methods import post_to_person
from tests.breedgraph.e2e.utils import get_verified_payload, assert_payload_success
from tests.breedgraph.scenarios.account_builder import AccountBuilder
from tests.breedgraph.scenarios.team_tree_builder import TeamTreeBuilder
from tests.breedgraph.scenarios.person_builder import PersonBuilder
from tests.breedgraph.utilities.inputs import UserInputGenerator


@pytest_asyncio.fixture(scope="module", loop_scope="session")
async def delete_context(isolated_state, uow_factory) -> dict:
    # An ontology admin who administers the team, so members can delete their accounts
    admin = await AccountBuilder(uow_factory).account_with_affiliations(ontology_role=OntologyRole.ADMIN)
    return {'user_id': admin['user_id'], 'team_id': admin['team_id']}


async def verified_account(uow_factory, ontology_role=OntologyRole.CONTRIBUTOR) -> tuple[int, str]:
    """A verified account and its password"""
    user_input = UserInputGenerator().new_user_input()
    async with uow_factory.get_uow() as uow:
        account = await uow.repositories.accounts.create(AccountInput(user=UserInput(
            name=user_input['name'],
            fullname=user_input['name'],
            email=user_input['email'],
            password_hash=user_input['password_hash'],
            ontology_role=ontology_role
        )))
        account.verify_email()
        await uow.commit()
    return account.user.id, user_input['password']


async def member_with_person(uow_factory, context) -> tuple[int, str, int]:
    """A team member who has written a Person record, linked to their account"""
    user_id, password = await verified_account(uow_factory)
    team_tree_builder = TeamTreeBuilder(uow_factory)
    for access in [Access.READ, Access.WRITE]:
        await team_tree_builder.authorise_access(user_id=user_id, team_id=context['team_id'], access=access)
    person_id = await PersonBuilder(uow_factory).person(user_id=user_id, team_id=context['team_id'])
    async with uow_factory.get_uow(user_id=context['user_id']) as uow:
        person = await uow.repositories.people.get(person_id=person_id)
        person.link(user_id)
        await uow.commit()
    return user_id, password, person_id


async def delete_account(client, token, password: str, erase_person: bool | None = None):
    variables = {'password': password}
    if erase_person is not None:
        variables['erasePerson'] = erase_person
    response = await _post(
        client, token,
        " mutation ( $password: String!, $erasePerson: Boolean ) { "
        "   accountsDeleteAccount( password: $password, erasePerson: $erasePerson ) "
        "   { status, result, errors { name, message } } "
        " } ",
        variables
    )
    return response, get_verified_payload(response, "accountsDeleteAccount")


async def get_person(client, token, person_id: int) -> dict:
    return get_verified_payload(await post_to_person(client, token, person_id), "peoplePerson")['result']


async def deleted_user_node(uow_factory, user_id: int) -> dict:
    async with uow_factory.get_uow() as uow:
        result = await uow.tx.run(
            "MATCH (user {id: $user_id}) WHERE user:User OR user:DeletedUser "
            "RETURN labels(user) AS labels, properties(user) AS props, "
            "COUNT { (user)-[:READ|WRITE|CURATE|ADMIN|IS_PERSON|CLAIMS]->() } AS links, "
            "COUNT { (user)-[:CONTRIBUTED]->() } AS contributions",
            user_id=user_id
        )
        return (await result.single()).data()


@pytest.mark.asyncio(loop_scope="session")
async def test_delete_account_erases_person_by_default(
        client, login_token_factory, uow_factory, state_store, event_queue, erasure_log_path, delete_context
):
    admin_token = login_token_factory(user_id=delete_context['user_id'])
    user_id, password, person_id = await member_with_person(uow_factory, delete_context)
    token = login_token_factory(user_id=user_id)
    submission_id = await state_store.store_submission(user_id, {'data': 'pending'})
    analysis_id = await state_store.store_analysis(user_id, {'config': 'pending'})

    response, payload = await delete_account(client, token, password + "wrong")
    assert payload['status'] == GQLStatus.ERROR.name
    assert 'Incorrect password' in payload['errors'][0]['message']

    response, payload = await delete_account(client, token, password)
    assert_payload_success(payload)
    await event_queue.join()
    assert 'auth_token=""' in response.headers.get('set-cookie', '') or 'Max-Age=0' in response.headers.get('set-cookie', '')

    node = await deleted_user_node(uow_factory, user_id)
    assert node['labels'] == ['DeletedUser']
    assert set(node['props']) == {'id', 'deleted_at'}
    assert node['links'] == 0
    # Provenance is kept
    assert node['contributions'] == 1
    # Working state is removed
    assert not await state_store.connection.exists(submission_id, analysis_id, f"user:{user_id}:submissions", f"user:{user_id}:analyses")

    person = await get_person(client, admin_token, person_id)
    assert person['erased'] is True
    assert person['linkedUser'] is None

    # The controller of a record written only by the deleted user still has its write history
    async with uow_factory.get_uow(user_id=delete_context['user_id']) as uow:
        controller = await uow.controls.get_controller(ControlledModelLabel.PERSON, person_id)
        assert user_id in [w.user for w in controller.writes]
        assert controller.created

    # The login token, still validly signed, is no longer accepted
    response, payload = await delete_account(client, token, password)
    assert payload['status'] == GQLStatus.ERROR.name

    # Both the deletion and the erasure are logged
    log = JsonLinesErasureLog(erasure_log_path).read()
    [deletion] = [e for e in log if isinstance(e, AccountDeletionLogEntry) and e.user_id == user_id]
    assert [e for e in log if isinstance(e, ErasureLogEntry) and e.person_id == person_id]
    assert deletion.deleted_at == node['props']['deleted_at'].to_native()
    # the account's creation time is logged, so a replay deletes this account and no other given its id
    assert deletion.created_at is not None

    # Simulate restoring a backup taken before the deletion, with the account as it was then
    async with uow_factory.get_uow() as uow:
        await uow.tx.run(
            "MATCH (user:DeletedUser {id: $user_id}), (team:Team {id: $team_id}) "
            "REMOVE user:DeletedUser SET user:User, user.name = 'Restored', user.email = 'restored@example.org', "
            "user.deleted_at = null, user.time = datetime($created_at) "
            "CREATE (user)-[:READ {authorisation: 'AUTHORISED', heritable: false}]->(team)",
            user_id=user_id, team_id=delete_context['team_id'], created_at=deletion.created_at.isoformat()
        )
        await uow.commit()
    assert (await deleted_user_node(uow_factory, user_id))['labels'] == ['User']

    applied = await apply_erasures(uow_factory.driver, [deletion])
    assert applied.accounts == 1
    node = await deleted_user_node(uow_factory, user_id)
    assert node['labels'] == ['DeletedUser']
    assert node['props'] == {'id': user_id, 'deleted_at': node['props']['deleted_at']}
    assert node['props']['deleted_at'].to_native() == deletion.deleted_at
    assert node['links'] == 0
    # Replaying is idempotent
    assert (await apply_erasures(uow_factory.driver, [deletion])).accounts == 0


@pytest.mark.asyncio(loop_scope="session")
async def test_delete_account_can_keep_person(client, login_token_factory, uow_factory, delete_context):
    admin_token = login_token_factory(user_id=delete_context['user_id'])
    user_id, password, person_id = await member_with_person(uow_factory, delete_context)

    response, payload = await delete_account(client, login_token_factory(user_id=user_id), password, erase_person=False)
    assert_payload_success(payload)

    person = await get_person(client, admin_token, person_id)
    assert person['erased'] is False
    assert person['name']
    assert person['linkedUser'] is None


@pytest.mark.asyncio(loop_scope="session")
async def test_delete_account_refused_for_sole_team_admin(client, login_token_factory, uow_factory, delete_context):
    user_id, password = await verified_account(uow_factory)
    team_id = await TeamTreeBuilder(uow_factory).team_tree(user_id=user_id)
    token = login_token_factory(user_id=user_id)

    response, payload = await delete_account(client, token, password)
    assert payload['status'] == GQLStatus.ERROR.name
    assert 'only admin' in payload['errors'][0]['message']
    assert str(team_id) in payload['errors'][0]['message']

    # Another admin lets them go
    other_id, _ = await verified_account(uow_factory)
    await TeamTreeBuilder(uow_factory).authorise_access(user_id=other_id, team_id=team_id, access=Access.ADMIN)
    response, payload = await delete_account(client, token, password)
    assert_payload_success(payload)


async def set_ontology_role(uow_factory, ontology_role: OntologyRole, user_id: int | None = None, name: str | None = None):
    async with uow_factory.get_uow() as uow:
        account = await uow.repositories.accounts.get(user_id=user_id, name=name)
        account.user.ontology_role = ontology_role
        await uow.commit()


@pytest.mark.asyncio(loop_scope="session")
async def test_delete_account_refused_for_last_ontology_admin(client, login_token_factory, uow_factory, delete_context):
    user_id, password = await verified_account(uow_factory, ontology_role=OntologyRole.ADMIN)
    token = login_token_factory(user_id=user_id)
    # Besides the context admin, the test setup's system account is an ontology admin
    await set_ontology_role(uow_factory, OntologyRole.EDITOR, user_id=delete_context['user_id'])
    await set_ontology_role(uow_factory, OntologyRole.EDITOR, name='system')
    try:
        response, payload = await delete_account(client, token, password)
        assert payload['status'] == GQLStatus.ERROR.name
        assert 'no ontology admins' in payload['errors'][0]['message']
    finally:
        await set_ontology_role(uow_factory, OntologyRole.ADMIN, user_id=delete_context['user_id'])
        await set_ontology_role(uow_factory, OntologyRole.ADMIN, name='system')

    # With another ontology admin, they can go
    response, payload = await delete_account(client, token, password)
    assert_payload_success(payload)
