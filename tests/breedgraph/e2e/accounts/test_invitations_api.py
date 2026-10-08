import pytest
import pytest_asyncio

from breedgraph.config import SITE_NAME
from breedgraph.domain.commands.accounts import RemoveExpiredInvitations
from breedgraph.domain.model.controls import Access
from breedgraph.entrypoints.fastapi.graphql.decorators import GQLStatus

from tests.breedgraph.e2e.accounts.post_methods import (
    post_to_create_account, post_to_invite, post_to_cancel_invitation, post_to_resend_invitation,
    post_to_invitation_preview, post_to_account_invitations
)
from tests.breedgraph.e2e.utils import get_verified_payload, assert_payload_success
from tests.breedgraph.scenarios.account_builder import AccountBuilder
from tests.breedgraph.scenarios.person_builder import PersonBuilder
from tests.breedgraph.utilities.mailhog_fetching import get_json_from_email
from tests.breedgraph.utilities.inputs import UserInputGenerator

INVITATION_SUBJECT = f"Invitation to register with {SITE_NAME}"


@pytest.fixture
def user_input_generator() -> UserInputGenerator:
    """A generator of our own, as other tests rely on the order of inputs from the shared one"""
    return UserInputGenerator()


@pytest_asyncio.fixture(scope="module", loop_scope="session")
async def invitation_context(isolated_state, uow_factory) -> dict:
    account_builder = AccountBuilder(uow_factory)
    inviter = await account_builder.account_with_affiliations()
    other = await account_builder.account_with_affiliations()
    # Invitations are required once a verified account exists
    async with uow_factory.get_uow() as uow:
        account = await uow.repositories.accounts.get(user_id=inviter['user_id'])
        account.verify_email()
        await uow.commit()
    return {
        'user_id': inviter['user_id'],
        'team_id': inviter['team_id'],
        'other_team_id': other['team_id'],
        'other_user_id': other['user_id']
    }


async def invite(client, token, email, **kwargs) -> dict:
    payload = get_verified_payload(await post_to_invite(client, token, email, **kwargs), "accountsInvite")
    assert_payload_success(payload)
    return await get_json_from_email(mailto=email, subject=INVITATION_SUBJECT)


async def pending_invitations(client, token) -> list:
    payload = get_verified_payload(await post_to_account_invitations(client, token), "accountsAccount")
    assert_payload_success(payload)
    return payload['result']['invitations']


async def register(client, user_input, invitation_token=None, accept_team_ids=None):
    return get_verified_payload(await post_to_create_account(
        client, user_input['name'], user_input['email'], user_input['password'],
        invitation_token=invitation_token, accept_team_ids=accept_team_ids
    ), "accountsCreateAccount")


async def user_affiliated(uow_factory, user_name: str, team_id: int, access: Access) -> bool:
    async with uow_factory.get_uow(redacted=False) as uow:
        account = await uow.repositories.accounts.get(name=user_name)
        organisation = await uow.repositories.organisations.get(team_id=team_id)
        return account.user.id in organisation.get_affiliates(team_id, access=access)


@pytest.mark.asyncio(loop_scope="session")
async def test_registration_requires_invitation(client, user_input_generator, invitation_context):
    payload = await register(client, user_input_generator.new_user_input())
    assert payload['status'] == GQLStatus.ERROR.name
    assert 'invited' in payload['errors'][0]['message']


@pytest.mark.asyncio(loop_scope="session")
async def test_invitation_with_team_accepted(client, login_token_factory, uow_factory, user_input_generator, invitation_context):
    token = login_token_factory(user_id=invitation_context['user_id'])
    user_input = user_input_generator.new_user_input()
    team_id = invitation_context['team_id']
    email = await invite(client, token, user_input['email'], teams=[{'teamId': team_id, 'access': 'READ'}])

    [pending] = [i for i in await pending_invitations(client, token) if i['email'] == user_input['email']]
    assert pending['teams'] == [{'team': {'id': str(team_id)}, 'access': 'READ'}]

    preview = get_verified_payload(await post_to_invitation_preview(client, email['token']), "accountsInvitation")
    assert_payload_success(preview)
    assert preview['result']['email'] == user_input['email']
    assert preview['result']['invitedBy'] is not None
    assert preview['result']['offersPerson'] is False
    assert [(t['teamId'], t['access']) for t in preview['result']['teams']] == [(str(team_id), 'READ')]

    assert_payload_success(await register(client, user_input, email['token'], accept_team_ids=[team_id]))
    assert await user_affiliated(uow_factory, user_input['name'], team_id, Access.READ)

    # The invitation, and the email address with it, is deleted once accepted
    assert user_input['email'] not in [i['email'] for i in await pending_invitations(client, token)]
    preview = get_verified_payload(await post_to_invitation_preview(client, email['token']), "accountsInvitation")
    assert preview['status'] == GQLStatus.ERROR.name


@pytest.mark.asyncio(loop_scope="session")
async def test_invited_team_can_be_declined(client, login_token_factory, uow_factory, user_input_generator, invitation_context):
    token = login_token_factory(user_id=invitation_context['user_id'])
    user_input = user_input_generator.new_user_input()
    team_id = invitation_context['team_id']
    email = await invite(client, token, user_input['email'], teams=[{'teamId': team_id, 'access': 'WRITE'}])

    assert_payload_success(await register(client, user_input, email['token']))
    assert not await user_affiliated(uow_factory, user_input['name'], team_id, Access.WRITE)


@pytest.mark.asyncio(loop_scope="session")
async def test_registration_requires_invited_email(client, login_token_factory, user_input_generator, invitation_context):
    token = login_token_factory(user_id=invitation_context['user_id'])
    invited = user_input_generator.new_user_input()
    email = await invite(client, token, invited['email'])

    other = user_input_generator.new_user_input()
    payload = await register(client, other, email['token'])
    assert payload['status'] == GQLStatus.ERROR.name
    assert 'email address the invitation was sent to' in payload['errors'][0]['message']


@pytest.mark.asyncio(loop_scope="session")
async def test_invite_rules(client, login_token_factory, uow_factory, user_input_generator, invitation_context):
    token = login_token_factory(user_id=invitation_context['user_id'])

    # Teams must be administered by the inviter
    payload = get_verified_payload(await post_to_invite(
        client, token, user_input_generator.new_user_input()['email'],
        teams=[{'teamId': invitation_context['other_team_id'], 'access': 'READ'}]
    ), "accountsInvite")
    assert payload['status'] == GQLStatus.ERROR.name

    # One pending invitation per email address from each inviter
    email = user_input_generator.new_user_input()['email']
    await invite(client, token, email)
    payload = get_verified_payload(await post_to_invite(client, token, email), "accountsInvite")
    assert payload['status'] == GQLStatus.ERROR.name
    assert 'resend' in payload['errors'][0]['message']

    # A Person must be controlled by a team the inviter administers
    other_person_id = await PersonBuilder(uow_factory).person(
        user_id=invitation_context['other_user_id'], team_id=invitation_context['other_team_id']
    )
    payload = get_verified_payload(await post_to_invite(
        client, token, user_input_generator.new_user_input()['email'], person_id=other_person_id
    ), "accountsInvite")
    assert payload['status'] == GQLStatus.ERROR.name

    person_id = await PersonBuilder(uow_factory).person(
        user_id=invitation_context['user_id'], team_id=invitation_context['team_id']
    )
    person_email = user_input_generator.new_user_input()['email']
    invitation = await invite(client, token, person_email, person_id=person_id)
    preview = get_verified_payload(await post_to_invitation_preview(client, invitation['token']), "accountsInvitation")
    assert preview['result']['offersPerson'] is True
    [pending] = [i for i in await pending_invitations(client, token) if i['email'] == person_email]
    assert pending['person'] == {'id': str(person_id)}


@pytest.mark.asyncio(loop_scope="session")
async def test_resend_and_cancel(client, login_token_factory, user_input_generator, invitation_context):
    token = login_token_factory(user_id=invitation_context['user_id'])
    email = user_input_generator.new_user_input()['email']
    first = await invite(client, token, email)
    [pending] = [i for i in await pending_invitations(client, token) if i['email'] == email]

    assert_payload_success(get_verified_payload(
        await post_to_resend_invitation(client, token, int(pending['id'])), "accountsResendInvitation"
    ))
    [resent] = [i for i in await pending_invitations(client, token) if i['email'] == email]
    assert resent['expiresAt'] > pending['expiresAt']

    # Only the inviter can cancel
    other_token = login_token_factory(user_id=invitation_context['other_user_id'])
    payload = get_verified_payload(await post_to_cancel_invitation(client, other_token, int(pending['id'])), "accountsCancelInvitation")
    assert payload['status'] == GQLStatus.ERROR.name

    assert_payload_success(get_verified_payload(
        await post_to_cancel_invitation(client, token, int(pending['id'])), "accountsCancelInvitation"
    ))
    assert email not in [i['email'] for i in await pending_invitations(client, token)]
    preview = get_verified_payload(await post_to_invitation_preview(client, first['token']), "accountsInvitation")
    assert preview['status'] == GQLStatus.ERROR.name


@pytest.mark.asyncio(loop_scope="session")
async def test_expired_invitations(client, bus, login_token_factory, uow_factory, user_input_generator, invitation_context):
    token = login_token_factory(user_id=invitation_context['user_id'])
    user_input = user_input_generator.new_user_input()
    email = await invite(client, token, user_input['email'])

    async with uow_factory.get_uow() as uow:
        await uow.tx.run(
            "MATCH (invitation:Invitation {email_lower: $email}) SET invitation.expires_at = datetime() - duration('P1D')",
            email=user_input['email'].casefold()
        )
        await uow.commit()

    assert user_input['email'] not in [i['email'] for i in await pending_invitations(client, token)]
    payload = await register(client, user_input, email['token'])
    assert payload['status'] == GQLStatus.ERROR.name

    await bus.handle(RemoveExpiredInvitations())
    async with uow_factory.get_uow() as uow:
        result = await uow.tx.run(
            "MATCH (invitation:Invitation {email_lower: $email}) RETURN count(invitation) AS remaining",
            email=user_input['email'].casefold()
        )
        assert (await result.single())['remaining'] == 0


@pytest.mark.asyncio(loop_scope="session")
async def test_invited_curate_access_includes_read(client, login_token_factory, uow_factory, user_input_generator, invitation_context):
    token = login_token_factory(user_id=invitation_context['user_id'])
    user_input = user_input_generator.new_user_input()
    team_id = invitation_context['team_id']
    email = await invite(client, token, user_input['email'], teams=[{'teamId': team_id, 'access': 'CURATE'}])
    assert_payload_success(await register(client, user_input, email['token'], accept_team_ids=[team_id]))
    assert await user_affiliated(uow_factory, user_input['name'], team_id, Access.CURATE)
    assert await user_affiliated(uow_factory, user_input['name'], team_id, Access.READ)
