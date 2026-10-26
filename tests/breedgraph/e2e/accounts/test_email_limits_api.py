"""
The emails a user's actions send to addresses they give are limited each hour (EMAIL_RATE_LIMIT_PER_HOUR): invitations
sent and resent, and the verification of a new email address, counted together. Password resets asked for one address
are limited too (PASSWORD_RESET_RATE_LIMIT_PER_HOUR), counted whether the address is registered or not, as anyone can
ask. The limits are lowered here, and counted in Redis, which each module starts empty.
"""
import pytest

from breedgraph import config
from breedgraph.config import GQL_API_PATH

from tests.breedgraph.e2e.accounts.post_methods import post_to_invite, post_to_resend_invitation, post_to_account_invitations
from tests.breedgraph.e2e.accounts.test_password_changes_api import account_with_password, post
from tests.breedgraph.e2e.utils import get_verified_payload, assert_payload_success
from tests.breedgraph.scenarios.account_builder import AccountBuilder

EMAILS = "You have reached the limit of emails per hour that invitations and address changes send, please try again later"
RESETS = "A password reset has been asked for this address too often, please try again in an hour"
REQUEST_RESET = (
    "mutation ( $email: String! ) { accountsRequestPasswordReset( email: $email ) { status, result, errors { message } } }"
)


def refusal(response, query_name: str) -> str:
    payload = get_verified_payload(response, query_name)
    assert payload['status'] == 'ERROR'
    return payload['errors'][0]['message']


@pytest.mark.asyncio(loop_scope="session")
async def test_invitations_sent_and_resent_count_towards_the_hourly_limit(
        client, uow_factory, login_token_factory, isolated_state, monkeypatch
):
    monkeypatch.setattr(config, 'EMAIL_RATE_LIMIT_PER_HOUR', 3)
    token = login_token_factory(await AccountBuilder(uow_factory).account())
    for email in ('first.invitee@example.org', 'second.invitee@example.org'):
        assert_payload_success(get_verified_payload(await post_to_invite(client, token, email), 'accountsInvite'))
    invitations = get_verified_payload(await post_to_account_invitations(client, token), 'accountsAccount')
    first = next(i for i in invitations['result']['invitations'] if i['email'] == 'first.invitee@example.org')
    response = await post_to_resend_invitation(client, token, first['id'])
    assert_payload_success(get_verified_payload(response, 'accountsResendInvitation'))

    assert refusal(await post_to_invite(client, token, 'third.invitee@example.org'), 'accountsInvite') == EMAILS
    assert refusal(await post_to_resend_invitation(client, token, first['id']), 'accountsResendInvitation') == EMAILS
    # another user has a limit of their own
    other = login_token_factory(await AccountBuilder(uow_factory).account())
    assert_payload_success(get_verified_payload(
        await post_to_invite(client, other, 'third.invitee@example.org'), 'accountsInvite'
    ))


@pytest.mark.asyncio(loop_scope="session")
async def test_a_new_email_address_counts_towards_the_hourly_limit(
        client, uow_factory, login_token_factory, isolated_state, monkeypatch
):
    monkeypatch.setattr(config, 'EMAIL_RATE_LIMIT_PER_HOUR', 1)
    user_id, password = await account_with_password(uow_factory)
    token = login_token_factory(user_id)
    change = (
        "mutation ( $email: String, $current: String ) { "
        "  accountsUpdateUser( email: $email, currentPassword: $current ) { status, result, errors { message } } "
        "}"
    )
    response = await post(client, token, change, {"email": "first.address@example.org", "current": password})
    assert_payload_success(get_verified_payload(response, 'accountsUpdateUser'))
    response = await post(client, token, change, {"email": "second.address@example.org", "current": password})
    assert refusal(response, 'accountsUpdateUser') == EMAILS


@pytest.mark.asyncio(loop_scope="session")
async def test_password_resets_asked_for_an_address_are_limited_whether_it_is_registered_or_not(
        client, isolated_state, monkeypatch
):
    monkeypatch.setattr(config, 'PASSWORD_RESET_RATE_LIMIT_PER_HOUR', 2)
    ask = lambda email: post(client, None, REQUEST_RESET, {"email": email})
    for _ in range(2):
        assert_payload_success(get_verified_payload(await ask('nobody@example.org'), 'accountsRequestPasswordReset'))
    # the same address, as typed another way
    assert refusal(await ask(' Nobody@Example.org '), 'accountsRequestPasswordReset') == RESETS
    assert_payload_success(get_verified_payload(await ask('somebody@example.org'), 'accountsRequestPasswordReset'))
