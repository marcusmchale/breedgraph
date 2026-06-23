import pytest

from src.breedgraph.domain.model.controls import ReadRelease
from src.breedgraph.domain.model.people import PersonStored
from src.breedgraph.custom_exceptions import NoResultFoundError

from tests.scenarios.person_builder import PersonBuilder

@pytest.mark.asyncio(loop_scope="session")
async def test_create_and_get(
        uow_factory,
        person_build_context
):
    user_id = person_build_context['user_id']
    team_id = person_build_context['team_id']
    person_input = PersonBuilder.person_input(team_id=team_id)
    async with uow_factory.get_uow(user_id=user_id) as uow:
        await uow.repositories.people.create(person_input)
        await uow.commit()

    async with uow_factory.get_uow(user_id=user_id) as uow:
        person = await uow.repositories.people.get(name=person_input.name)
        assert person
        assert person.teams
        assert team_id in person.teams

        async for person in uow.repositories.people.get_all():
            if person.name == person_input.name:
                break
        else:
            raise NoResultFoundError("Couldn't find created person by get all")

@pytest.mark.asyncio(loop_scope="session")
async def test_get_unregistered_and_without_read_access(
        uow_factory,
        person_build_context
    ):
    user_id_1 = person_build_context['user_id_1']
    user_id_2 = person_build_context['user_id_2']
    person_input = PersonBuilder.person_input()
    # Create person as user 1
    async with uow_factory.get_uow(user_id=user_id_1) as uow:
        person = await uow.repositories.people.create(person_input)
        await uow.commit()
        person_id = person.id

    # Confirm unregistered users get None
    async with uow_factory.get_uow() as uow:
        person = await uow.repositories.people.get(name=person_input.name)
        assert person is None

    # Confirm user 2 without read access sees a redacted version when get by id but None in discovery query
    async with uow_factory.get_uow(user_id=user_id_2) as uow:
        person = await uow.repositories.people.get(person_id=person_id)
        assert person is not None
        assert person.name == PersonStored._redacted_str

        person = await uow.repositories.people.get(name=person_input.name)
        assert person is None


@pytest.mark.asyncio(loop_scope="session")
async def test_release_to_registered(
        uow_factory,
        person_build_context
):
    user_id_1 = person_build_context['user_id_1']
    team_id = person_build_context['team_id']
    user_id_2 = person_build_context['user_id_2']
    person_input = PersonBuilder.person_input()

    # Create person as user 1 released to registered users
    async with uow_factory.get_uow(user_id=user_id_1) as uow:
        person = await uow.repositories.people.create(person_input)
        await uow.controls.set_controls(person, control_teams={team_id}, release=ReadRelease.REGISTERED)
        await uow.commit()
        person_id = person.id

    # Confirm unregistered users get None
    async with uow_factory.get_uow() as uow:
        person = await uow.repositories.people.get(name=person_input.name)
        assert person is None

    # Confirm user 2 without explicit read access now sees the full version and can get by discovery
    async with uow_factory.get_uow(user_id=user_id_2) as uow:
        person = await uow.repositories.people.get(person_id=person_id)
        assert person is not None
        assert person.name == person_input.name

        person = await uow.repositories.people.get(name=person_input.name)
        assert person is not None
        assert person.name == person_input.name


@pytest.mark.asyncio(loop_scope="session")
async def test_release_to_public(
        uow_factory,
        person_build_context
):
    user_id_1 = person_build_context['user_id_1']
    team_id = person_build_context['team_id']
    user_id_2 = person_build_context['user_id_2']
    person_input = PersonBuilder.person_input()

    # Create person as user 1 released to public users
    async with uow_factory.get_uow(user_id=user_id_1) as uow:
        person = await uow.repositories.people.create(person_input)
        await uow.controls.set_controls(person, control_teams={team_id}, release=ReadRelease.PUBLIC)
        await uow.commit()
        person_id = person.id

    # Confirm unregistered users get full form and can match by discovery
    async with uow_factory.get_uow() as uow:
        person = await uow.repositories.people.get(person_id=person_id)
        assert person is not None
        assert person.name == person_input.name

        person = await uow.repositories.people.get(name=person_input.name)
        assert person is not None
        assert person.name == person_input.name

    # Confirm user 2 without explicit read access gets the same
    async with uow_factory.get_uow(user_id=user_id_2) as uow:
        person = await uow.repositories.people.get(person_id=person_id)
        assert person is not None
        assert person.name == person_input.name

        person = await uow.repositories.people.get(name=person_input.name)
        assert person is not None
        assert person.name == person_input.name

@pytest.mark.asyncio(loop_scope="session")
async def test_edit_person_name(
        uow_factory,
        person_build_context
):
    user_id = person_build_context['user_id']
    person_input_1 = PersonBuilder.person_input()
    person_input_2 = PersonBuilder.person_input()

    # Create person
    async with uow_factory.get_uow(user_id=user_id) as uow:
        person = await uow.repositories.people.create(person_input_1)
        await uow.commit()
        person_id = person.id

    # Change name
    async with uow_factory.get_uow(user_id=user_id) as uow:
        person = await uow.repositories.people.get(person_id=person_id)
        person.name = person_input_2.name
        await uow.commit()

    # Validate the change
    async with uow_factory.get_uow(user_id=user_id) as uow:
        person = await uow.repositories.people.get(person_id=person_id)
        assert person.name == person_input_2.name
