"""The ontology's editors and admins, as an ontology admin lists them on Manage Roles"""
import pytest

from breedgraph.domain.model.accounts import OntologyRole

from tests.breedgraph.e2e.utils import get_verified_payload, assert_payload_success, with_auth, GQL_API_PATH
from tests.breedgraph.scenarios.account_builder import AccountBuilder


async def listed(client, token, operation: str) -> set[str]:
    response = await client.post(
        GQL_API_PATH,
        json={"query": f"query {{ {operation} {{ status, result {{ id ontologyRole }}, errors {{ message }} }} }}"},
        headers=with_auth(csrf_token=client.headers["X-CSRF-Token"], auth_token=token)
    )
    payload = get_verified_payload(response, operation)
    assert_payload_success(payload)
    return {user['id'] for user in payload['result']}


@pytest.mark.asyncio(loop_scope="session")
async def test_editors_and_admins_are_listed(ontology_build_context, login_token_factory, uow_factory, client):
    builder = AccountBuilder(uow_factory=uow_factory)
    editor_id = await builder.account(ontology_role=OntologyRole.EDITOR)
    admin_id = await builder.account(ontology_role=OntologyRole.ADMIN)
    token = login_token_factory(ontology_build_context['user_id'])

    assert str(editor_id) in await listed(client, token, 'ontologyEditors')
    admins = await listed(client, token, 'ontologyAdmins')
    assert str(admin_id) in admins and str(editor_id) not in admins
