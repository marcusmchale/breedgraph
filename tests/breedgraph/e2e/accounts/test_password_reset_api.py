import bcrypt
import pytest
from itsdangerous import URLSafeTimedSerializer

from breedgraph import config
from breedgraph.config import GQL_API_PATH

from tests.breedgraph.e2e.utils import get_verified_payload, assert_payload_success
from tests.breedgraph.scenarios.account_builder import AccountBuilder


@pytest.mark.asyncio(loop_scope="session")
async def test_reset_password_with_token(client, uow_factory, isolated_state):
    user_id = await AccountBuilder(uow_factory).account()
    token = URLSafeTimedSerializer(config.SECRET_KEY).dumps(user_id, salt=config.PASSWORD_RESET_SALT)
    new_password = 'A-new-Passw0rd!'

    response = await client.post(GQL_API_PATH, json={
        "query": (
            " mutation ( $token: String!, $password: String! ) { "
            "  accountsResetPassword( token: $token, password: $password ) { status, result, errors { name, message } } "
            " } "
        ),
        "variables": {"token": token, "password": new_password}
    })
    assert_payload_success(get_verified_payload(response, "accountsResetPassword"))

    async with uow_factory.get_uow() as uow:
        account = await uow.repositories.accounts.get(user_id=user_id)
    assert bcrypt.checkpw(new_password.encode(), account.user.password_hash.encode())
