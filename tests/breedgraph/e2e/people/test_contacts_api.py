import pytest
import pytest_asyncio

from breedgraph import config
from breedgraph.config import SITE_NAME
from breedgraph.domain.commands.programs import CreateProgram
from breedgraph.domain.model.controls import ControlledModelLabel, ReadRelease
from breedgraph.entrypoints.fastapi.graphql.decorators import GQLStatus

from tests.breedgraph.e2e.people.post_methods import _post
from tests.breedgraph.e2e.utils import get_verified_payload, assert_payload_success
from tests.breedgraph.scenarios.account_builder import AccountBuilder
from tests.breedgraph.scenarios.person_builder import PersonBuilder
from tests.breedgraph.scenarios.program_builder import ProgramBuilder
from tests.breedgraph.utilities.mailhog_fetching import get_email


async def set_release(uow_factory, user_id: int, team_id: int, label: ControlledModelLabel, entity_id: int, release: ReadRelease):
    async with uow_factory.get_uow(user_id=user_id) as uow:
        await uow.controls.set_controls_by_id_and_label(
            ids=[entity_id], label=label, control_teams={team_id}, release=release
        )
        await uow.commit()


async def linked_person(uow_factory, context, release: ReadRelease = ReadRelease.REGISTERED) -> tuple[int, int]:
    """A Person linked to a new account, returning the person id and user id"""
    contact_user_id = await AccountBuilder(uow_factory).account()
    person_id = await PersonBuilder(uow_factory).person(user_id=context['user_id'], team_id=context['team_id'])
    async with uow_factory.get_uow(user_id=context['user_id']) as uow:
        person = await uow.repositories.people.get(person_id=person_id)
        person.link(contact_user_id)
        await uow.commit()
    if release is not ReadRelease.PRIVATE:
        await set_release(uow_factory, context['user_id'], context['team_id'], ControlledModelLabel.PERSON, person_id, release)
    return person_id, contact_user_id


@pytest_asyncio.fixture(scope="module", loop_scope="session")
async def contacts_context(isolated_state, uow_factory) -> dict:
    admin = await AccountBuilder(uow_factory).account_with_affiliations()
    return {'user_id': admin['user_id'], 'team_id': admin['team_id']}


async def create_program(bus, uow_factory, context, contact_ids, release=ReadRelease.REGISTERED) -> int:
    name = ProgramBuilder.program_input().name
    await bus.handle(CreateProgram(
        agent_id=context['user_id'], write_team=context['team_id'], release=release, name=name, contact_ids=contact_ids
    ))
    async with uow_factory.get_uow(user_id=context['user_id']) as uow:
        # get(name=...) does not match, as programs are stored without name_lower
        [program_id] = [program.id async for program in uow.repositories.programs.get_all() if program.name == name]
        return program_id


async def contact(client, token, person_id, program_id, subject='About your program', message='Could we talk about it?'):
    response = await _post(
        client, token,
        " mutation ( $personId: ID!, $entityId: ID!, $subject: String!, $message: String! ) { "
        "  peopleContactPerson( personId: $personId, entityLabel: PROGRAM, entityId: $entityId, subject: $subject, message: $message ) "
        "  { status, result, errors { name, message } } } ",
        {"personId": person_id, "entityId": program_id, "subject": subject, "message": message}
    )
    return get_verified_payload(response, "peopleContactPerson")


@pytest.mark.asyncio(loop_scope="session")
async def test_contacts_must_be_linked(bus, uow_factory, contacts_context):
    unlinked_id = await PersonBuilder(uow_factory).person(user_id=contacts_context['user_id'], team_id=contacts_context['team_id'])
    with pytest.raises(Exception, match="not linked to an account"):
        await create_program(bus, uow_factory, contacts_context, [unlinked_id])


@pytest.mark.asyncio(loop_scope="session")
async def test_contacts_must_be_visible_with_the_program(bus, uow_factory, contacts_context):
    private_id, _ = await linked_person(uow_factory, contacts_context, ReadRelease.PRIVATE)
    with pytest.raises(Exception, match="at least REGISTERED"):
        await create_program(bus, uow_factory, contacts_context, [private_id], release=ReadRelease.PRIVATE)

    registered_id, _ = await linked_person(uow_factory, contacts_context, ReadRelease.REGISTERED)
    with pytest.raises(Exception, match="at least PUBLIC"):
        await create_program(bus, uow_factory, contacts_context, [registered_id], release=ReadRelease.PUBLIC)

    program_id = await create_program(bus, uow_factory, contacts_context, [registered_id])
    async with uow_factory.get_uow(user_id=contacts_context['user_id']) as uow:
        assert (await uow.repositories.programs.get(program_id=program_id)).contact_ids == [registered_id]


@pytest.mark.asyncio(loop_scope="session")
async def test_message_a_contact(bus, client, login_token_factory, uow_factory, contacts_context):
    person_id, contact_user_id = await linked_person(uow_factory, contacts_context)
    program_id = await create_program(bus, uow_factory, contacts_context, [person_id])
    sender_id = await AccountBuilder(uow_factory).account()
    sender_token = login_token_factory(user_id=sender_id)

    assert_payload_success(await contact(client, sender_token, person_id, program_id, subject='Seed request'))

    async with uow_factory.get_uow() as uow:
        recipient_email = (await uow.repositories.accounts.get(user_id=contact_user_id)).user.email
        sender_email = (await uow.repositories.accounts.get(user_id=sender_id)).user.email
    email = await get_email(recipient_email, f"{SITE_NAME}: Seed request")
    assert email['Content']['Headers']['Reply-To'] == [sender_email]
    assert sender_email not in email['Raw']['To']


@pytest.mark.asyncio(loop_scope="session")
async def test_message_rules(bus, client, login_token_factory, uow_factory, contacts_context, monkeypatch):
    person_id, _ = await linked_person(uow_factory, contacts_context)
    program_id = await create_program(bus, uow_factory, contacts_context, [person_id])
    other_person_id, _ = await linked_person(uow_factory, contacts_context)
    private_program_id = await create_program(
        bus, uow_factory, contacts_context, [other_person_id], release=ReadRelease.PRIVATE
    )
    sender_token = login_token_factory(user_id=await AccountBuilder(uow_factory).account())

    # Only contacts of the given program
    payload = await contact(client, sender_token, other_person_id, program_id)
    assert payload['status'] == GQLStatus.ERROR.name and 'not a contact' in payload['errors'][0]['message']
    # Only programs the sender can read
    payload = await contact(client, sender_token, other_person_id, private_program_id)
    assert payload['status'] == GQLStatus.ERROR.name
    # Length
    payload = await contact(client, sender_token, person_id, program_id, message='x' * (config.MESSAGE_MAX_LENGTH + 1))
    assert payload['status'] == GQLStatus.ERROR.name and 'limited' in payload['errors'][0]['message']
    # Rate limit: attempts with a valid subject and message count, so far two above, then one sent
    monkeypatch.setattr(config, 'MESSAGE_RATE_LIMIT_PER_HOUR', 3)
    assert_payload_success(await contact(client, sender_token, person_id, program_id))
    payload = await contact(client, sender_token, person_id, program_id)
    assert payload['status'] == GQLStatus.ERROR.name and 'limit of messages' in payload['errors'][0]['message']


@pytest.mark.asyncio(loop_scope="session")
async def test_remove_self_as_contact(bus, client, login_token_factory, uow_factory, contacts_context):
    person_id, contact_user_id = await linked_person(uow_factory, contacts_context)
    program_id = await create_program(bus, uow_factory, contacts_context, [person_id])
    token = login_token_factory(user_id=contact_user_id)

    async def remove():
        response = await _post(
            client, token,
            " mutation ( $entityId: ID! ) { peopleRemoveSelfAsContact( entityLabel: PROGRAM, entityId: $entityId ) "
            " { status, result, errors { name, message } } } ",
            {"entityId": program_id}
        )
        return get_verified_payload(response, "peopleRemoveSelfAsContact")

    assert_payload_success(await remove())
    async with uow_factory.get_uow(user_id=contacts_context['user_id']) as uow:
        assert (await uow.repositories.programs.get(program_id=program_id)).contact_ids == []
    payload = await remove()
    assert payload['status'] == GQLStatus.ERROR.name
