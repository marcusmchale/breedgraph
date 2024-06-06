import pytest
import pytest_asyncio

from src.breedgraph.domain.model.controls import Release
from src.breedgraph.domain.model.people import Person, PersonStored

from src.breedgraph.adapters.repositories.people import Neo4jPeopleRepository

from src.breedgraph.custom_exceptions import NoResultFoundError, UnauthorisedOperationError

@pytest.mark.asyncio(scope="session")
async def test_create_and_get_person(
        neo4j_tx,
        stored_account_with_affiliations,
        stored_account_without_affiliations,
        user_input_generator
):
    repo = Neo4jPeopleRepository(neo4j_tx, account=stored_account_with_affiliations)

    person_input = user_input_generator.new_user_input()
    person = Person(
        name=person_input['name'],
        fullname=person_input['name'],
        email=person_input['email'],
        user=1,
        teams=[1]
    )
    # Person is created private
    stored: PersonStored = await repo.create(person)
    retrieved_private: PersonStored = await repo.get(person_id = stored.id)

    assert stored.name == retrieved_private.name
    async for person in repo.get_all():
        if person.name == person_input['name']:
            break
    else:
        raise NoResultFoundError("Couldn't find created person by get all")

    # Confirm other registered users cannot see it yet
    registered_repo = Neo4jPeopleRepository(neo4j_tx, account=stored_account_without_affiliations)
    with pytest.raises(Exception) as e_info:
        await registered_repo.get(person_id = stored.id)
    assert e_info.type == UnauthorisedOperationError
    async for _ in registered_repo.get_all():
        raise UnauthorisedOperationError("A registered user with no affiliations can get all including the private person")

    # Confirm the public can't see it yet
    public_repo = Neo4jPeopleRepository(neo4j_tx, account=None)
    with pytest.raises(Exception) as e_info:
        await public_repo.get(person_id = stored.id)
    assert e_info.type == UnauthorisedOperationError
    async for _ in public_repo.get_all():
        raise UnauthorisedOperationError("Public users can get all including the private person")

@pytest.mark.asyncio(scope="session")
async def test_release_to_registered(
        neo4j_tx,
        stored_account_with_affiliations,
        stored_account_without_affiliations,
        user_input_generator
):
    repo = Neo4jPeopleRepository(neo4j_tx, account=stored_account_with_affiliations)
    person = await repo.get(person_id=1)

    await repo.set_release(person, Release.REGISTERED)
    retrieved: PersonStored = await repo.get(person_id=person.id)
    assert retrieved
    async for p in repo.get_all():
        if p.name == person.name:
            break
        else:
            raise NoResultFoundError("Couldn't find person by get all in private")

    # Confirm other registered users cannot see it yet
    registered_repo = Neo4jPeopleRepository(neo4j_tx, account=stored_account_without_affiliations)
    retrieved_from_registered = await registered_repo.get(person_id=person.id)
    assert retrieved_from_registered
    async for p in registered_repo.get_all():
        if p.name == person.name:
            break
        else:
            raise NoResultFoundError("Couldn't find created person by get all")

    # Confirm the public can't see it yet
    public_repo = Neo4jPeopleRepository(neo4j_tx, account=None)
    with pytest.raises(Exception) as e_info:
        await public_repo.get(person_id=person.id)
    assert e_info.type == UnauthorisedOperationError
    async for _ in public_repo.get_all():
        raise UnauthorisedOperationError("Public users can get all including the private person")


@pytest.mark.asyncio(scope="session")
async def test_release_to_public(
        neo4j_tx,
        stored_account_with_affiliations,
        stored_account_without_affiliations,
        user_input_generator
):
    repo = Neo4jPeopleRepository(neo4j_tx, account=stored_account_with_affiliations)
    person = await repo.get(person_id=1)

    assert person
    await repo.set_release(person, Release.PUBLIC)
    retrieved: PersonStored = await repo.get(person_id=person.id)
    assert retrieved
    async for p in repo.get_all():
        if p.name == person.name:
            break
        else:
            raise NoResultFoundError("Couldn't find person by get all in private")


    # Confirm other registered users cannot see it yet
    registered_repo = Neo4jPeopleRepository(neo4j_tx, account=stored_account_without_affiliations)
    retrieved_from_registered = await registered_repo.get(person_id=person.id)
    assert retrieved_from_registered
    async for p in registered_repo.get_all():
        if p.name == person.name:
            break
        else:
            raise NoResultFoundError("Couldn't find created person by get all in registered")

    # Confirm the public can't see it yet
    public_repo = Neo4jPeopleRepository(neo4j_tx, account=None)
    retrieved_from_public = await public_repo.get(person_id=person.id)
    assert retrieved_from_public
    async for p in public_repo.get_all():
        if p.name == person.name:
            break
        else:
            raise NoResultFoundError("Couldn't find created person by get all in public")


@pytest.mark.asyncio(scope="session")
async def test_edit_person(neo4j_tx, stored_account_with_affiliations, user_input_generator):
    people_repo = Neo4jPeopleRepository(neo4j_tx, account = stored_account_with_affiliations)
    person = await people_repo.get(person_id=1)

    new_input = user_input_generator.new_user_input()
    person.name = new_input['name']
    await people_repo.update_seen()
    changed_person = await people_repo.get(person_id=1)
    assert changed_person.name == new_input['name']

