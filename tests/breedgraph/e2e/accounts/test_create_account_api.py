import pytest

from breedgraph.config import GQL_API_PATH

from tests.breedgraph.e2e.utils import get_verified_payload, assert_payload_success
from tests.breedgraph.utilities.inputs import UserInputGenerator


@pytest.mark.asyncio(loop_scope="session")
async def test_create_account_without_fullname(client, uow_factory, isolated_state):
    user_input = UserInputGenerator().new_user_input()
    response = await client.post(GQL_API_PATH, json={
        "query": (
            " mutation ( $name: String!, $email: String!, $password: String! ) { "
            "  accountsCreateAccount( name: $name, email: $email, password: $password ) "
            "  { status, result, errors { name, message } } "
            " } "
        ),
        "variables": {"name": user_input['name'], "email": user_input['email'], "password": user_input['password']}
    })
    assert_payload_success(get_verified_payload(response, "accountsCreateAccount"))

    async with uow_factory.get_uow() as uow:
        account = await uow.repositories.accounts.get(name=user_input['name'])
    assert account.user.fullname == user_input['name']
