import pytest
from src.breedgraph.domain.model.controls import Control, ReadRelease, Controller
from src.breedgraph.domain.model.people import PersonInput, PersonStored

from src.breedgraph.adapters.repositories.people import Neo4jPeopleRepository

from src.breedgraph.custom_exceptions import NoResultFoundError, UnauthorisedOperationError

def get_person_input(user_input_generator, user_id, team_id):
    person_input = user_input_generator.new_user_input()
    return PersonInput(
        name=person_input['name'],
        fullname=person_input['name'],
        email=person_input['email'],
        user=user_id,
        teams=[team_id]
    )

@pytest.mark.asyncio(scope="session")
async def test_create_and_get(
        people_repo,
        stored_person,
        stored_account,
        stored_organisation,
        user_input_generator
):
    person_input = get_person_input(user_input_generator, user_id=stored_account.user.id, team_id=stored_organisation.root.id)
    stored_person: PersonStored = await people_repo.create(person_input)
    retrieved_person: PersonStored = await people_repo.get(person_id = stored_person.id)
    assert stored_person.name == retrieved_person.name
    async for person in people_repo.get_all():
        if person.name == person_input.name:
            break
    else:
        raise NoResultFoundError("Couldn't find created person by get all")

@pytest.mark.asyncio(scope="session")
async def test_get_without_read(
            neo4j_tx,
            stored_account,
            stored_organisation,
            user_input_generator
    ):
    # Confirm without read we see a redacted version if registered and get None if not
    repo = Neo4jPeopleRepository(
        neo4j_tx,
        user_id=stored_account.user.id
    )
    retrieved = await repo.get(person_id=1)
    assert retrieved.name == PersonStored._redacted_str
    repo = Neo4jPeopleRepository(
        neo4j_tx
    )
    assert await repo.get(person_id=1) is None


@pytest.mark.asyncio(scope="session")
async def test_release_to_registered(
        neo4j_tx,
        stored_account,
        second_account,
        stored_person,
        people_repo,
        stored_organisation,
        user_input_generator
):
    stored_person.set_release(team_id=stored_organisation.root.id, release=ReadRelease.REGISTERED)
    await people_repo.update_seen()
    retrieved: PersonStored = await people_repo.get(person_id=stored_person.id)
    assert retrieved.name == stored_person.name
    async for p in people_repo.get_all():
        if p.name == stored_person.name:
            break
    else:
        raise NoResultFoundError("Private repo couldn't get person by get all")

    registered_repo = Neo4jPeopleRepository(neo4j_tx, user_id=second_account.user.id)
    retrieved_from_registered = await registered_repo.get(person_id=stored_person.id)
    assert retrieved_from_registered
    async for p in registered_repo.get_all():
        if p.name == stored_person.name:
            break
    else:
        raise NoResultFoundError("Registered repo can't get person by get all")

    # Confirm the public can't see it yet
    public_repo = Neo4jPeopleRepository(neo4j_tx)
    retrieved_from_unregistered =  await public_repo.get(person_id=stored_person.id)

    assert retrieved_from_unregistered is None
    async for _ in public_repo.get_all():
        import pdb; pdb.set_trace()
        raise UnauthorisedOperationError("Public repo can get private released person")


@pytest.mark.asyncio(scope="session")
async def test_release_to_public(
        neo4j_tx,
        stored_account,
        second_account,
        stored_organisation,
        user_input_generator
):
    repo = Neo4jPeopleRepository(
        neo4j_tx,
        user_id=stored_account.user.id,
        read_teams={stored_organisation.root.id},
        write_teams={stored_organisation.root.id},
        admin_teams={stored_organisation.root.id}
    )
    person = await repo.get(person_id=1)
    person.set_release(team_id=stored_organisation.root.id, release=ReadRelease.PUBLIC)
    await repo.update_seen()

    retrieved: PersonStored = await repo.get(person_id=person.id)
    assert retrieved
    async for p in repo.get_all():
        if p.name == person.name:
            break
    else:
        raise NoResultFoundError("Private repo can't get person by get all")

    # Confirm other registered users can see the un-redacted version
    registered_repo = Neo4jPeopleRepository(neo4j_tx, user_id = second_account.user.id)
    retrieved_from_registered = await registered_repo.get(person_id=person.id)
    assert retrieved_from_registered.name == person.name
    async for p in registered_repo.get_all():
        if p.name == person.name:
            break
    else:
        raise NoResultFoundError("Registered repo can't get person by get all")

    # Confirm the public can see it
    public_repo = Neo4jPeopleRepository(neo4j_tx)
    retrieved_from_public = await public_repo.get(person_id=person.id)
    assert retrieved_from_public
    async for p in public_repo.get_all():
        if p.name == person.name:
            break
    else:
        raise NoResultFoundError("Public repo can't get person by get all")


@pytest.mark.asyncio(scope="session")
async def test_edit_person(neo4j_tx, stored_account, stored_organisation, user_input_generator):
    repo = Neo4jPeopleRepository(
        neo4j_tx,
        user_id=stored_account.user.id,
        read_teams={stored_organisation.root.id},
        write_teams={stored_organisation.root.id},
        curate_teams={stored_organisation.root.id}
    )
    person = await repo.get(person_id=1)

    new_input = user_input_generator.new_user_input()
    person.name = new_input['name']
    await repo.update_seen()
    changed_person = await repo.get(person_id=1)
    assert changed_person.name == new_input['name']


