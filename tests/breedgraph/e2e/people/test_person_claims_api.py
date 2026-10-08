import pytest
import pytest_asyncio

from breedgraph.config import SITE_NAME
from breedgraph.entrypoints.fastapi.graphql.decorators import GQLStatus

from tests.breedgraph.e2e.accounts.post_methods import post_to_create_account, post_to_invite
from tests.breedgraph.e2e.people.post_methods import _post, post_to_person, PERSON_FIELDS
from tests.breedgraph.e2e.utils import get_verified_payload, assert_payload_success
from tests.breedgraph.scenarios.account_builder import AccountBuilder
from tests.breedgraph.scenarios.person_builder import PersonBuilder
from tests.breedgraph.utilities.inputs import UserInputGenerator
from tests.breedgraph.utilities.mailhog_fetching import confirm_email_delivered, get_json_from_email


@pytest_asyncio.fixture(scope="module", loop_scope="session")
async def claims_context(isolated_state, uow_factory) -> dict:
    account_builder = AccountBuilder(uow_factory)
    admin = await account_builder.account_with_affiliations()
    # Invitations are required once a verified account exists
    async with uow_factory.get_uow() as uow:
        account = await uow.repositories.accounts.get(user_id=admin['user_id'])
        account.verify_email()
        await uow.commit()
    return {'user_id': admin['user_id'], 'team_id': admin['team_id']}


async def new_person(uow_factory, context) -> int:
    return await PersonBuilder(uow_factory).person(user_id=context['user_id'], team_id=context['team_id'])


async def mutate(client, token, field: str, **variables):
    arguments = ', '.join(f'{name}: ${name}' for name in variables)
    declarations = ', '.join(f'${name}: ID!' for name in variables)
    response = await _post(
        client, token,
        f" mutation ( {declarations} ) {{ {field}( {arguments} ) {{ status, result, errors {{ name, message }} }} }} ",
        variables
    )
    return get_verified_payload(response, field)


async def query(client, token, field: str, selection: str):
    response = await _post(client, token, f" query {{ {field} {{ status, result {{ {selection} }}, errors {{ name, message }} }} }} ")
    payload = get_verified_payload(response, field)
    assert payload['status'] == GQLStatus.SUCCESS.name, payload
    return payload['result']


@pytest.mark.asyncio(loop_scope="session")
async def test_claim_approved(client, login_token_factory, uow_factory, claims_context):
    admin_token = login_token_factory(user_id=claims_context['user_id'])
    claimant_id = await AccountBuilder(uow_factory).account()
    claimant_token = login_token_factory(user_id=claimant_id)
    person_id = await new_person(uow_factory, claims_context)
    person_name = get_verified_payload(await post_to_person(client, admin_token, person_id), "peoplePerson")['result']['name']

    assert_payload_success(await mutate(client, claimant_token, "peopleRequestClaim", personId=person_id))
    assert [c['person']['id'] for c in await query(client, claimant_token, "peopleMyClaims", "person { id } requestedAt")] == [str(person_id)]

    requests = await query(client, admin_token, "peopleClaimRequests", "person { id name } userId name fullname requestedAt")
    [request] = [r for r in requests if r['userId'] == str(claimant_id)]
    assert request['person'] == {'id': str(person_id), 'name': person_name}
    assert request['name'] and request['requestedAt']
    async with uow_factory.get_uow() as uow:
        admin_email = (await uow.repositories.accounts.get(user_id=claims_context['user_id'])).user.email
        claimant_email = (await uow.repositories.accounts.get(user_id=claimant_id)).user.email
    assert await confirm_email_delivered(admin_email, f"{SITE_NAME} request to link a Person record")

    # Requesting from the id-only form leaves the record intact
    assert get_verified_payload(await post_to_person(client, admin_token, person_id), "peoplePerson")['result']['name'] == person_name

    assert_payload_success(await mutate(client, admin_token, "peopleApproveClaim", personId=person_id, userId=claimant_id))
    my_person = await query(client, claimant_token, "peopleMyPerson", PERSON_FIELDS)
    assert my_person['id'] == str(person_id)
    assert my_person['name'] == person_name
    assert my_person['restricted'] is False
    assert await query(client, claimant_token, "peopleMyClaims", "person { id }") == []
    assert await confirm_email_delivered(
        claimant_email, f"{SITE_NAME} Person record linked to your account", string_in_body="message you"
    )

    # One Person per account
    payload = await mutate(client, claimant_token, "peopleRequestClaim", personId=await new_person(uow_factory, claims_context))
    assert payload['status'] == GQLStatus.ERROR.name
    assert 'already linked' in payload['errors'][0]['message']

    # The linked user can unlink
    assert_payload_success(await mutate(client, claimant_token, "peopleUnlinkPerson", personId=person_id))
    assert await query(client, claimant_token, "peopleMyPerson", "id") is None


@pytest.mark.asyncio(loop_scope="session")
async def test_claim_rejected_and_withdrawn(client, login_token_factory, uow_factory, claims_context):
    admin_token = login_token_factory(user_id=claims_context['user_id'])
    claimant_id = await AccountBuilder(uow_factory).account()
    claimant_token = login_token_factory(user_id=claimant_id)
    person_id = await new_person(uow_factory, claims_context)

    assert_payload_success(await mutate(client, claimant_token, "peopleRequestClaim", personId=person_id))
    # Only admins of the controlling teams decide
    payload = await mutate(client, claimant_token, "peopleApproveClaim", personId=person_id, userId=claimant_id)
    assert payload['status'] == GQLStatus.ERROR.name
    assert_payload_success(await mutate(client, admin_token, "peopleRejectClaim", personId=person_id, userId=claimant_id))
    assert await query(client, claimant_token, "peopleMyClaims", "person { id }") == []

    assert_payload_success(await mutate(client, claimant_token, "peopleRequestClaim", personId=person_id))
    assert_payload_success(await mutate(client, claimant_token, "peopleWithdrawClaim", personId=person_id))
    assert await query(client, claimant_token, "peopleMyClaims", "person { id }") == []


@pytest.mark.asyncio(loop_scope="session")
@pytest.mark.parametrize("link_person", [True, False])
async def test_invitation_links_person_when_chosen(client, login_token_factory, uow_factory, claims_context, link_person):
    admin_token = login_token_factory(user_id=claims_context['user_id'])
    person_id = await new_person(uow_factory, claims_context)
    user_input = UserInputGenerator().new_user_input()
    assert_payload_success(get_verified_payload(
        await post_to_invite(client, admin_token, user_input['email'], person_id=person_id), "accountsInvite"
    ))
    invitation = await get_json_from_email(mailto=user_input['email'], subject=f"Invitation to register with {SITE_NAME}")

    response = await _post(
        client, None,
        " mutation ( $name: String!, $email: String!, $password: String!, $token: String, $linkPerson: Boolean ) { "
        "  accountsCreateAccount( name: $name, email: $email, password: $password, invitationToken: $token, linkPerson: $linkPerson ) "
        "  { status, result, errors { name, message } } } ",
        {"name": user_input['name'], "email": user_input['email'], "password": user_input['password'],
         "token": invitation['token'], "linkPerson": link_person}
    )
    assert_payload_success(get_verified_payload(response, "accountsCreateAccount"))

    async with uow_factory.get_uow() as uow:
        user_id = (await uow.repositories.accounts.get(name=user_input['name'])).user.id
    my_person = await query(client, login_token_factory(user_id=user_id), "peopleMyPerson", "id")
    assert (my_person == {'id': str(person_id)}) if link_person else my_person is None


@pytest.mark.asyncio(loop_scope="session")
async def test_link_person_requires_offer(client, login_token_factory, claims_context):
    admin_token = login_token_factory(user_id=claims_context['user_id'])
    user_input = UserInputGenerator().new_user_input()
    assert_payload_success(get_verified_payload(await post_to_invite(client, admin_token, user_input['email']), "accountsInvite"))
    invitation = await get_json_from_email(mailto=user_input['email'], subject=f"Invitation to register with {SITE_NAME}")
    response = await _post(
        client, None,
        " mutation ( $name: String!, $email: String!, $password: String!, $token: String ) { "
        "  accountsCreateAccount( name: $name, email: $email, password: $password, invitationToken: $token, linkPerson: true ) "
        "  { status, result, errors { name, message } } } ",
        {"name": user_input['name'], "email": user_input['email'], "password": user_input['password'], "token": invitation['token']}
    )
    payload = get_verified_payload(response, "accountsCreateAccount")
    assert payload['status'] == GQLStatus.ERROR.name
    assert 'does not offer a Person' in payload['errors'][0]['message']
