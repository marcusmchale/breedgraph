import pytest

from breedgraph.custom_exceptions import NoResultFoundError, UnauthorisedOperationError, IllegalOperationError
from breedgraph.domain.model.controls import ReadRelease, ControlledModelLabel, Access
from breedgraph.domain.model.people import PersonStored

from tests.breedgraph.scenarios.person_builder import PersonBuilder


async def create_person(uow_factory, context, team_in_affiliation: bool = True) -> tuple[int, str]:
    person_input = PersonBuilder.person_input(team_id=context['team_id'] if team_in_affiliation else None)
    async with uow_factory.get_uow(user_id=context['user_id'], write_team=context['team_id']) as uow:
        person = await uow.repositories.people.create(person_input)
        await uow.commit()
    return person.id, person_input.name


@pytest.mark.asyncio(loop_scope="session")
async def test_create_and_get(uow_factory, person_build_context):
    user_id = person_build_context['user_id']
    team_id = person_build_context['team_id']
    person_id, name = await create_person(uow_factory, person_build_context)

    async with uow_factory.get_uow(user_id=user_id) as uow:
        person = await uow.repositories.people.get(name=name)
        assert person.id == person_id
        assert person.teams == [team_id]
        assert person.informed_attestation
        assert person.recorded_by == user_id
        assert person.recorded_at is not None
        assert not person.erased

        async for person in uow.repositories.people.get_all():
            if person.name == name:
                break
        else:
            raise NoResultFoundError("Couldn't find created person by get all")


@pytest.mark.asyncio(loop_scope="session")
async def test_get_missing_returns_none(uow_factory, person_build_context):
    async with uow_factory.get_uow(user_id=person_build_context['user_id']) as uow:
        assert await uow.repositories.people.get(person_id=-1) is None


@pytest.mark.asyncio(loop_scope="session")
async def test_name_search_is_not_a_pattern(uow_factory, person_build_context):
    await create_person(uow_factory, person_build_context)
    async with uow_factory.get_uow(user_id=person_build_context['user_id']) as uow:
        assert await uow.repositories.people.get(name='.*') is None


@pytest.mark.asyncio(loop_scope="session")
async def test_unregistered_and_without_read_access(uow_factory, person_build_context):
    person_id, name = await create_person(uow_factory, person_build_context)

    # The repository returns whole aggregates by id, for writes; reads redact explicitly.
    # Unregistered users get nothing
    async with uow_factory.get_uow() as uow:
        person = await uow.repositories.people.get(person_id=person_id)
        assert person.name == name
        assert await uow.repositories.people.redacted(person) is None
        assert await uow.repositories.people.get(name=name) is None

    # Registered users without read access see the ID only, and cannot find it by name
    async with uow_factory.get_uow(user_id=person_build_context['user_id_2']) as uow:
        person = await uow.repositories.people.redacted(await uow.repositories.people.get(person_id=person_id))
        assert person.id == person_id
        assert person.name is None
        assert person.teams == []
        assert person.recorded_by is None
        assert await uow.repositories.people.get(name=name) is None


@pytest.mark.asyncio(loop_scope="session")
async def test_release(uow_factory, person_build_context):
    """Released to registered users, a Person is read by them but not by anonymous users; it goes no wider"""
    person_id, name = await create_person(uow_factory, person_build_context)
    async with uow_factory.get_uow(user_id=person_build_context['user_id']) as uow:
        await uow.controls.set_controls_by_id_and_label(
            ids=[person_id], label=ControlledModelLabel.PERSON,
            control_teams={person_build_context['team_id']}, release=ReadRelease.REGISTERED
        )
        with pytest.raises(IllegalOperationError, match="at most to registered"):
            await uow.controls.set_controls_by_id_and_label(
                ids=[person_id], label=ControlledModelLabel.PERSON,
                control_teams={person_build_context['team_id']}, release=ReadRelease.PUBLIC
            )
        await uow.commit()

    async with uow_factory.get_uow(user_id=person_build_context['user_id_2']) as uow:
        assert (await uow.repositories.people.get(person_id=person_id)).name == name
        assert (await uow.repositories.people.get(name=name)).id == person_id

    async with uow_factory.get_uow() as uow:
        assert await uow.repositories.people.redacted(await uow.repositories.people.get(person_id=person_id)) is None


@pytest.mark.asyncio(loop_scope="session")
async def test_edit_person(uow_factory, person_build_context):
    user_id = person_build_context['user_id']
    person_id, _ = await create_person(uow_factory, person_build_context)
    new_name = PersonBuilder.person_input().name

    async with uow_factory.get_uow(user_id=user_id) as uow:
        person = await uow.repositories.people.get(person_id=person_id)
        person.name = new_name
        person.teams = []
        await uow.commit()

    async with uow_factory.get_uow(user_id=user_id) as uow:
        person = await uow.repositories.people.get(person_id=person_id)
        assert person.name == new_name
        assert person.teams == []


@pytest.mark.asyncio(loop_scope="session")
async def test_persons_cannot_be_removed(uow_factory, person_build_context):
    person_id, _ = await create_person(uow_factory, person_build_context)
    async with uow_factory.get_uow(user_id=person_build_context['user_id']) as uow:
        person = await uow.repositories.people.get(person_id=person_id)
        with pytest.raises(Exception, match="erased rather than removed"):
            await uow.repositories.people.remove(person)


@pytest.mark.asyncio(loop_scope="session")
async def test_erase_by_admin(uow_factory, person_build_context):
    user_id = person_build_context['user_id']
    person_id, name = await create_person(uow_factory, person_build_context)

    async with uow_factory.get_uow(user_id=user_id) as uow:
        person = await uow.repositories.people.get(person_id=person_id)
        controller = await uow.controls.get_controller(person.label, person.id)
        person.erase(agent_id=user_id, controller=controller, admin_teams=uow.controls.access_teams[Access.ADMIN])
        await uow.commit()

    async with uow_factory.get_uow(user_id=user_id) as uow:
        person = await uow.repositories.people.get(person_id=person_id)
        assert person.erased
        assert person.name is None
        assert person.teams == []
        assert person.recorded_by == user_id
        assert await uow.repositories.people.get(name=name) is None


@pytest.mark.asyncio(loop_scope="session")
async def test_linked_user_reads_and_erases_own_record(uow_factory, person_build_context):
    user_id = person_build_context['user_id']
    subject_id = person_build_context['user_id_2']
    person_id, name = await create_person(uow_factory, person_build_context)

    async with uow_factory.get_uow(user_id=user_id) as uow:
        person = await uow.repositories.people.get(person_id=person_id)
        person.user = subject_id
        await uow.commit()

    # The linked user has no affiliation to the controlling team, but sees the full record
    async with uow_factory.get_uow(user_id=subject_id) as uow:
        person = await uow.repositories.people.get(person_id=person_id)
        assert person.name == name
        assert person.user == subject_id
        controller = await uow.controls.get_controller(person.label, person.id)
        person.erase(agent_id=subject_id, controller=controller, admin_teams=uow.controls.access_teams[Access.ADMIN])
        await uow.commit()

    async with uow_factory.get_uow(user_id=user_id) as uow:
        person = await uow.repositories.people.get(person_id=person_id)
        assert person.erased
        assert person.name is None
        assert person.user is None


@pytest.mark.asyncio(loop_scope="session")
async def test_other_users_cannot_store_changes(uow_factory, person_build_context):
    person_id, _ = await create_person(uow_factory, person_build_context)
    async with uow_factory.get_uow(user_id=person_build_context['user_id']) as uow:
        await uow.controls.set_controls_by_id_and_label(
            ids=[person_id], label=ControlledModelLabel.PERSON,
            control_teams={person_build_context['team_id']}, release=ReadRelease.REGISTERED
        )
        await uow.commit()

    async with uow_factory.get_uow(user_id=person_build_context['user_id_2']) as uow:
        person = await uow.repositories.people.get(person_id=person_id)
        person.name = 'Changed'
        with pytest.raises(UnauthorisedOperationError):
            await uow.commit()
