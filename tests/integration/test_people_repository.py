import pytest
import pytest_asyncio

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
    account = stored_account_with_affiliations
    people_repo = Neo4jPeopleRepository(neo4j_tx, user=account.user.id)

    person_input = user_input_generator.new_user_input()
    person = Person(
        name=person_input['name'],
        fullname=person_input['name'],
        email=person_input['email'],
        user=1
    )
    person_stored = await people_repo.create(person)
    import pdb; pdb.set_trace()
    person_retrieved = await people_repo.get(person_id = person_stored.id)
    assert person_stored.name == person_retrieved.name
    async for person in people_repo.get_all(reader=stored_account_with_affiliations.user.id):
        if person.name == person_input['name']:
            break
    else:
        raise NoResultFoundError("Couldn't find created person by get all")
    async for _ in people_repo.get_all(reader=stored_account_without_affiliations.user.id):
        raise UnauthorisedOperationError("A user with no affiliations can see the registered person")

#@pytest.mark.asyncio(scope="session")
#async def test_edit_person(neo4j_tx, stored_account_with_affiliations, user_input_generator):
#    people_repo = Neo4jPeopleRepository(neo4j_tx)
#    person = await people_repo.get(person_id = 1, reader=stored_account_with_affiliations.user.id)
#
#    new_input = user_input_generator.new_user_input()
#    person.name = new_input['name']
#    person.contributors.append
#    await people_repo.update_seen()
#    changed_person = await people_repo.get(person_id=1, reader=stored_account_with_affiliations.user.id)
#    assert changed_person.name == new_input['name']

