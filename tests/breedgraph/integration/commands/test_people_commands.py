import pytest
import pytest_asyncio

from breedgraph.adapters.files import JsonLinesErasureLog
from breedgraph.adapters.neo4j.erasures import apply_erasures, erase_person
from breedgraph.service_layer.infrastructure.erasure_log import ErasureLogEntry
from breedgraph.custom_exceptions import IllegalOperationError, NoResultFoundError, UnauthorisedOperationError
from breedgraph.domain.commands.people import CreatePerson, UpdatePerson, ErasePerson
from breedgraph.domain.commands.controls import SetRelease
from breedgraph.domain.model.control_transfers import ControlledEntity, ControlScope
from breedgraph.domain.model.controls import ControlledModelLabel, Access, ReadRelease

from tests.breedgraph.scenarios.account_builder import AccountBuilder
from tests.breedgraph.scenarios.person_builder import PersonBuilder

async def team_account(uow_factory) -> dict:
    """An account administering a team tree, which can record Persons"""
    return await AccountBuilder(uow_factory).account_with_affiliations()


async def create_person(bus, uow_factory, account: dict, **kwargs) -> int:
    name = PersonBuilder.person_input().name
    await bus.handle(CreatePerson(
        agent_id=account['user_id'],
        write_team=account['team_id'],
        name=name,
        informed_attestation=True,
        **kwargs
    ))
    async with uow_factory.get_uow(user_id=account['user_id']) as uow:
        return (await uow.repositories.people.get(name=name)).id


async def get_person(uow_factory, user_id: int, person_id: int):
    async with uow_factory.get_uow(user_id=user_id) as uow:
        return await uow.repositories.people.get(person_id=person_id)


@pytest.mark.asyncio(loop_scope="session")
async def test_create(bus, uow_factory, isolated_state):
    account = await team_account(uow_factory)
    person_id = await create_person(
        bus, uow_factory, account, teams=[account['team_id']], institution='A University'
    )
    person = await get_person(uow_factory, account['user_id'], person_id)
    assert person.institution == 'A University'
    assert person.teams == [account['team_id']]
    assert person.recorded_by == account['user_id']


@pytest.mark.asyncio(loop_scope="session")
async def test_create_requires_existing_teams(bus, uow_factory, isolated_state):
    account = await team_account(uow_factory)
    with pytest.raises(NoResultFoundError, match="Teams not found"):
        await bus.handle(CreatePerson(
            agent_id=account['user_id'], write_team=account['team_id'], name='A Technician',
            informed_attestation=True, teams=[-1]
        ))


@pytest.mark.asyncio(loop_scope="session")
async def test_create_requires_informed_attestation(bus, uow_factory, isolated_state):
    account = await team_account(uow_factory)
    with pytest.raises(IllegalOperationError, match="informed"):
        await bus.handle(CreatePerson(agent_id=account['user_id'], write_team=account['team_id'], name='A Technician'))


@pytest.mark.asyncio(loop_scope="session")
async def test_update(bus, uow_factory, isolated_state):
    account = await team_account(uow_factory)
    person_id = await create_person(bus, uow_factory, account, teams=[account['team_id']])
    await bus.handle(UpdatePerson(
        agent_id=account['user_id'], person_id=person_id, name='Renamed', institution='A University',
        teams=[]
    ))
    person = await get_person(uow_factory, account['user_id'], person_id)
    assert person.name == 'Renamed'
    assert person.institution == 'A University'
    assert person.teams == []

    # An empty string removes the institution, and leaving it out keeps it
    await bus.handle(UpdatePerson(agent_id=account['user_id'], person_id=person_id, name='Renamed Again'))
    assert (await get_person(uow_factory, account['user_id'], person_id)).institution == 'A University'
    await bus.handle(UpdatePerson(agent_id=account['user_id'], person_id=person_id, institution=' '))
    assert (await get_person(uow_factory, account['user_id'], person_id)).institution is None


@pytest.mark.asyncio(loop_scope="session")
async def test_linked_user_can_change_name_and_institution_only(bus, uow_factory, isolated_state):
    account = await team_account(uow_factory)
    subject_id = await AccountBuilder(uow_factory).account()
    person_id = await create_person(bus, uow_factory, account)
    async with uow_factory.get_uow(user_id=account['user_id']) as uow:
        person = await uow.repositories.people.get(person_id=person_id)
        person.user = subject_id
        await uow.commit()

    await bus.handle(UpdatePerson(agent_id=subject_id, person_id=person_id, name='Preferred Name', institution='A University'))
    person = await get_person(uow_factory, subject_id, person_id)
    assert person.name == 'Preferred Name'
    assert person.institution == 'A University'

    with pytest.raises(UnauthorisedOperationError):
        await bus.handle(UpdatePerson(agent_id=subject_id, person_id=person_id, teams=[]))


@pytest.mark.asyncio(loop_scope="session")
async def test_erase_logs_and_replays(bus, uow_factory, event_queue, isolated_state, erasure_log_path):
    account = await team_account(uow_factory)
    person_id = await create_person(bus, uow_factory, account, teams=[account['team_id']], institution='A University')

    await bus.handle(ErasePerson(agent_id=account['user_id'], person_id=person_id))
    await event_queue.join()

    person = await get_person(uow_factory, account['user_id'], person_id)
    assert person.erased and person.name is None and person.institution is None and person.teams == []
    [entry] = [
        entry for entry in JsonLinesErasureLog(erasure_log_path).read()
        if isinstance(entry, ErasureLogEntry) and entry.person_id == person_id
    ]
    assert entry.erased_at == person.erased_at
    assert entry.created_at == person.recorded_at

    with pytest.raises(IllegalOperationError, match="erased"):
        await bus.handle(UpdatePerson(agent_id=account['user_id'], person_id=person_id, name='Restored'))

    # Simulate restoring a backup taken before the erasure
    async with uow_factory.get_uow() as uow:
        await uow.tx.run(
            "MATCH (person:Person {id: $person_id}), (team:Team {id: $team_id}) "
            "SET person.name = 'Restored Name', person.institution = 'A University', person.erased_at = null "
            "CREATE (person)-[:IN_TEAM]->(team)",
            person_id=person_id, team_id=account['team_id']
        )
        await uow.commit()
    assert (await get_person(uow_factory, account['user_id'], person_id)).name == 'Restored Name'

    applied = await apply_erasures(bus.uow_factory.driver, [entry])
    assert applied.persons == 1
    person = await get_person(uow_factory, account['user_id'], person_id)
    assert person.erased and person.name is None and person.institution is None and person.teams == []
    assert person.erased_at == entry.erased_at


@pytest.mark.asyncio(loop_scope="session")
async def test_operator_erasure_is_logged(bus, uow_factory, isolated_state, erasure_log_path):
    """For requests made to the University (scripts/erase_person.py): erased and logged like any other erasure"""
    account = await team_account(uow_factory)
    person_id = await create_person(bus, uow_factory, account, teams=[account['team_id']], institution='A University')
    claimant_id = await AccountBuilder(uow_factory).account()
    linked_user_id = await AccountBuilder(uow_factory).account()
    async with uow_factory.get_uow(user_id=account['user_id']) as uow:
        person = await uow.repositories.people.get(person_id=person_id)
        person.link(linked_user_id)
        await uow.commit()
    async with uow_factory.get_uow() as uow:
        await uow.tx.run(
            "MATCH (user:User {id: $user_id}), (person:Person {id: $person_id}) CREATE (user)-[:CLAIMS]->(person)",
            user_id=claimant_id, person_id=person_id
        )
        await uow.commit()

    erasure_log = JsonLinesErasureLog(erasure_log_path)
    assert await erase_person(bus.uow_factory.driver, erasure_log, person_id) is True
    person = await get_person(uow_factory, account['user_id'], person_id)
    assert person.erased and person.name is None and person.institution is None and person.teams == []
    assert person.user is None and person.claims == []
    [entry] = [e for e in erasure_log.read() if isinstance(e, ErasureLogEntry) and e.person_id == person_id]
    assert entry.created_at == person.recorded_at

    # erasing again changes and logs nothing
    assert await erase_person(bus.uow_factory.driver, erasure_log, person_id) is False
    assert len([e for e in erasure_log.read() if isinstance(e, ErasureLogEntry) and e.person_id == person_id]) == 1
    with pytest.raises(NoResultFoundError):
        await erase_person(bus.uow_factory.driver, erasure_log, -1)


@pytest.mark.asyncio(loop_scope="session")
async def test_erase_requires_admin_or_linked_user(bus, uow_factory, isolated_state):
    account = await team_account(uow_factory)
    other_user_id = await AccountBuilder(uow_factory).account()
    person_id = await create_person(bus, uow_factory, account)
    with pytest.raises(UnauthorisedOperationError):
        await bus.handle(ErasePerson(agent_id=other_user_id, person_id=person_id))
    assert not (await get_person(uow_factory, account['user_id'], person_id)).erased


@pytest.mark.asyncio(loop_scope="session")
async def test_person_control_can_be_shared_between_team_trees(bus, uow_factory, isolated_state):
    """The University holds every Person (docs/person.md §2), so control can be shared with any team"""
    account = await team_account(uow_factory)
    other = await team_account(uow_factory)
    person = ControlledEntity(label=ControlledModelLabel.PERSON, id=await create_person(bus, uow_factory, account))

    async with uow_factory.get_uow(user_id=account['user_id']) as uow:
        transfer = await uow.controls.offer_transfer(
            entities=[person], from_teams={account['team_id']}, recipient_team=other['team_id'], keep_from_teams=True
        )
        await uow.commit()
    async with uow_factory.get_uow(user_id=other['user_id']) as uow:
        await uow.controls.accept_transfer(transfer.id, to_teams={other['team_id']})
        await uow.commit()
    async with uow_factory.get_uow() as uow:
        assert (await uow.controls.get_controller(person.label, person.id)).teams == {account['team_id'], other['team_id']}


@pytest.mark.asyncio(loop_scope="session")
async def test_person_release_is_at_most_registered(bus, uow_factory, isolated_state):
    """Persons are never shown to anonymous users (docs/person.md §3): no path releases one to the public"""
    account = await team_account(uow_factory)
    with pytest.raises(IllegalOperationError, match="at most to registered"):
        await create_person(bus, uow_factory, account, release=ReadRelease.PUBLIC)

    person_id = await create_person(bus, uow_factory, account, release=ReadRelease.REGISTERED)
    with pytest.raises(IllegalOperationError, match="at most to registered"):
        await bus.handle(SetRelease(
            agent_id=account['user_id'], entity_ids=[person_id], entity_label=ControlledModelLabel.PERSON,
            release=ReadRelease.PUBLIC
        ))
    with pytest.raises(IllegalOperationError, match="at most to registered"):
        await bus.handle(SetRelease(
            agent_id=account['user_id'],
            scope=ControlScope(team_id=account['team_id'], label=ControlledModelLabel.PERSON),
            release=ReadRelease.PUBLIC
        ))

    other = await team_account(uow_factory)
    person = ControlledEntity(label=ControlledModelLabel.PERSON, id=person_id)
    async with uow_factory.get_uow(user_id=account['user_id']) as uow:
        transfer = await uow.controls.offer_transfer(
            entities=[person], from_teams={account['team_id']}, recipient_team=other['team_id']
        )
        await uow.commit()
    async with uow_factory.get_uow(user_id=other['user_id']) as uow:
        with pytest.raises(IllegalOperationError, match="at most to registered"):
            await uow.controls.accept_transfer(transfer.id, to_teams={other['team_id']}, release=ReadRelease.PUBLIC)
    async with uow_factory.get_uow() as uow:
        assert (await uow.controls.get_controller(person.label, person.id)).release is ReadRelease.REGISTERED
