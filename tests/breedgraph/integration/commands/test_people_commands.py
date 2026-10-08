import pytest
import pytest_asyncio

from breedgraph import config
from breedgraph.adapters.files import JsonLinesErasureLog
from breedgraph.adapters.neo4j.erasures import apply_person_erasures
from breedgraph.custom_exceptions import IllegalOperationError, NoResultFoundError, UnauthorisedOperationError
from breedgraph.domain.commands.organisations import DeclareLegalEntity, LegalEntity
from breedgraph.domain.commands.people import CreatePerson, UpdatePerson, ErasePerson
from breedgraph.domain.model.control_transfers import ControlledEntity
from breedgraph.domain.model.controls import ControlledModelLabel
from breedgraph.domain.model.people import LawfulBasis

from tests.breedgraph.scenarios.account_builder import AccountBuilder
from tests.breedgraph.scenarios.person_builder import PersonBuilder

TERMS_VERSION = 'test-terms-1'


@pytest.fixture(autouse=True)
def terms_version(monkeypatch):
    monkeypatch.setattr(config, 'DATA_PROCESSING_TERMS_VERSION', TERMS_VERSION)


async def declared_account(bus, uow_factory) -> dict:
    """An account administering an organisation with a declared legal entity"""
    account = await AccountBuilder(uow_factory).account_with_affiliations()
    await bus.handle(DeclareLegalEntity(
        agent_id=account['user_id'],
        team_id=account['team_id'],
        legal_entity=LegalEntity(
            legal_name='Test University', privacy_contact='dataprotection@test.example', terms_version=TERMS_VERSION
        )
    ))
    return account


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
async def test_create_requires_declared_legal_entity(bus, uow_factory, isolated_state):
    account = await AccountBuilder(uow_factory).account_with_affiliations()
    with pytest.raises(IllegalOperationError, match="legal entity"):
        await bus.handle(CreatePerson(
            agent_id=account['user_id'], write_team=account['team_id'], name='A Technician', informed_attestation=True
        ))


@pytest.mark.asyncio(loop_scope="session")
async def test_create(bus, uow_factory, isolated_state):
    account = await declared_account(bus, uow_factory)
    person_id = await create_person(
        bus, uow_factory, account, teams=[account['team_id']], basis=LawfulBasis.LEGITIMATE_INTEREST
    )
    person = await get_person(uow_factory, account['user_id'], person_id)
    assert person.teams == [account['team_id']]
    assert person.basis is LawfulBasis.LEGITIMATE_INTEREST
    assert person.recorded_by == account['user_id']


@pytest.mark.asyncio(loop_scope="session")
async def test_create_requires_existing_teams(bus, uow_factory, isolated_state):
    account = await declared_account(bus, uow_factory)
    with pytest.raises(NoResultFoundError, match="Teams not found"):
        await bus.handle(CreatePerson(
            agent_id=account['user_id'], write_team=account['team_id'], name='A Technician',
            informed_attestation=True, teams=[-1]
        ))


@pytest.mark.asyncio(loop_scope="session")
async def test_create_requires_informed_attestation(bus, uow_factory, isolated_state):
    account = await declared_account(bus, uow_factory)
    with pytest.raises(IllegalOperationError, match="informed"):
        await bus.handle(CreatePerson(agent_id=account['user_id'], write_team=account['team_id'], name='A Technician'))


@pytest.mark.asyncio(loop_scope="session")
async def test_update(bus, uow_factory, isolated_state):
    account = await declared_account(bus, uow_factory)
    person_id = await create_person(bus, uow_factory, account, teams=[account['team_id']])
    await bus.handle(UpdatePerson(
        agent_id=account['user_id'], person_id=person_id, name='Renamed', teams=[], basis=LawfulBasis.LEGITIMATE_INTEREST
    ))
    person = await get_person(uow_factory, account['user_id'], person_id)
    assert person.name == 'Renamed'
    assert person.teams == []
    assert person.basis is LawfulBasis.LEGITIMATE_INTEREST


@pytest.mark.asyncio(loop_scope="session")
async def test_linked_user_can_change_name_only(bus, uow_factory, isolated_state):
    account = await declared_account(bus, uow_factory)
    subject_id = await AccountBuilder(uow_factory).account()
    person_id = await create_person(bus, uow_factory, account)
    async with uow_factory.get_uow(user_id=account['user_id']) as uow:
        person = await uow.repositories.people.get(person_id=person_id)
        person.user = subject_id
        await uow.commit()

    await bus.handle(UpdatePerson(agent_id=subject_id, person_id=person_id, name='Preferred Name'))
    assert (await get_person(uow_factory, subject_id, person_id)).name == 'Preferred Name'

    with pytest.raises(UnauthorisedOperationError):
        await bus.handle(UpdatePerson(agent_id=subject_id, person_id=person_id, teams=[]))


@pytest.mark.asyncio(loop_scope="session")
async def test_erase_logs_and_replays(bus, uow_factory, event_queue, isolated_state, erasure_log_path):
    account = await declared_account(bus, uow_factory)
    person_id = await create_person(bus, uow_factory, account, teams=[account['team_id']])

    await bus.handle(ErasePerson(agent_id=account['user_id'], person_id=person_id))
    await event_queue.join()

    person = await get_person(uow_factory, account['user_id'], person_id)
    assert person.erased and person.name is None and person.teams == []
    [entry] = [entry for entry in JsonLinesErasureLog(erasure_log_path).read() if entry.person_id == person_id]
    assert entry.erased_at == person.erased_at

    with pytest.raises(IllegalOperationError, match="erased"):
        await bus.handle(UpdatePerson(agent_id=account['user_id'], person_id=person_id, name='Restored'))

    # Simulate restoring a backup taken before the erasure
    async with uow_factory.get_uow() as uow:
        await uow.tx.run(
            "MATCH (person:Person {id: $person_id}), (team:Team {id: $team_id}) "
            "SET person.name = 'Restored Name', person.erased_at = null "
            "CREATE (person)-[:IN_TEAM]->(team)",
            person_id=person_id, team_id=account['team_id']
        )
        await uow.commit()
    assert (await get_person(uow_factory, account['user_id'], person_id)).name == 'Restored Name'

    erased = await apply_person_erasures(bus.uow_factory.driver, [entry])
    assert erased == 1
    person = await get_person(uow_factory, account['user_id'], person_id)
    assert person.erased and person.name is None and person.teams == []
    assert person.erased_at == entry.erased_at


@pytest.mark.asyncio(loop_scope="session")
async def test_erase_requires_admin_or_linked_user(bus, uow_factory, isolated_state):
    account = await declared_account(bus, uow_factory)
    other_user_id = await AccountBuilder(uow_factory).account()
    person_id = await create_person(bus, uow_factory, account)
    with pytest.raises(UnauthorisedOperationError):
        await bus.handle(ErasePerson(agent_id=other_user_id, person_id=person_id))
    assert not (await get_person(uow_factory, account['user_id'], person_id)).erased


@pytest.mark.asyncio(loop_scope="session")
async def test_person_transfer_requires_recipient_legal_entity(bus, uow_factory, isolated_state):
    account = await declared_account(bus, uow_factory)
    undeclared = await AccountBuilder(uow_factory).account_with_affiliations()
    declared = await declared_account(bus, uow_factory)
    person = ControlledEntity(label=ControlledModelLabel.PERSON, id=await create_person(bus, uow_factory, account))

    async with uow_factory.get_uow(user_id=account['user_id']) as uow:
        with pytest.raises(IllegalOperationError, match="declared its legal entity"):
            await uow.controls.offer_transfer(
                entities=[person], from_teams={account['team_id']}, recipient_team=undeclared['team_id']
            )
        with pytest.raises(IllegalOperationError, match="same organisation"):
            await uow.controls.offer_transfer(
                entities=[person], from_teams={account['team_id']}, recipient_team=declared['team_id'],
                keep_from_teams=True
            )
        transfer = await uow.controls.offer_transfer(
            entities=[person], from_teams={account['team_id']}, recipient_team=declared['team_id']
        )
        await uow.commit()

    async with uow_factory.get_uow(user_id=declared['user_id']) as uow:
        await uow.controls.accept_transfer(transfer.id, to_teams={declared['team_id']})
        await uow.commit()
    async with uow_factory.get_uow() as uow:
        controller = await uow.controls.get_controller(person.label, person.id)
    assert controller.teams == {declared['team_id']}
