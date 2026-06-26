import pytest

from breedgraph.domain.model import ReadRelease, Access
from breedgraph.domain.model.germplasm import (
    GermplasmInput, GermplasmStored, GermplasmSourceType, GermplasmRelationship
)

from breedgraph.custom_exceptions import UnauthorisedOperationError

from tests.scenarios.germplasm_builder import GermplasmBuilder
from tests.scenarios.authorisation_manager import AuthorisationManager

@pytest.mark.asyncio(loop_scope="session")
async def test_create_and_get(
        uow_factory,
        germplasm_build_context
):
        user_id = germplasm_build_context['user_id']
        germplasm_input = GermplasmBuilder.germplasm_input()
        async with uow_factory.get_uow(user_id=user_id) as uow:
            germplasm_entry = await uow.germplasm.create_entry(germplasm_input)
            await uow.commit()

        async with uow_factory.get_uow(user_id=user_id) as uow:
            germplasm = await uow.germplasm.get_entry(germplasm_entry.id)
            assert germplasm
            assert germplasm.name == germplasm_input.name

@pytest.mark.asyncio(loop_scope="session")
async def test_create_relationship(
        uow_factory,
        germplasm_build_context
):
    user_id = germplasm_build_context['user_id']
    germplasm_input_1 = GermplasmBuilder.germplasm_input()
    germplasm_input_2 = GermplasmBuilder.germplasm_input()
    async with uow_factory.get_uow(user_id=user_id) as uow:
        germplasm_1 = await uow.germplasm.create_entry(germplasm_input_1)
        germplasm_2 = await uow.germplasm.create_entry(germplasm_input_2)
        germplasm_relationship = GermplasmBuilder.relationship_input(
            source_id=germplasm_1.id,
            sink_id=germplasm_2.id
        )
        await uow.germplasm.create_relationship(germplasm_relationship)
        await uow.commit()

    async with uow_factory.get_uow(user_id=user_id) as uow:
        germplasm_1 = await uow.germplasm.get_entry(entry_id=germplasm_1.id)
        germplasm_2 = await uow.germplasm.get_entry(entry_id=germplasm_2.id)
        assert germplasm_1
        assert germplasm_2
        try:
            source_relationship = await anext(uow.germplasm.get_source_relationships(germplasm_2.id))
            assert source_relationship.source_id == germplasm_1.id
            assert source_relationship.sink_id == germplasm_2.id
        except StopAsyncIteration:
            raise ValueError("Source relationship not found")
        try:
            sink_relationship = await anext(uow.germplasm.get_sink_relationships(germplasm_1.id))
            assert sink_relationship.source_id == germplasm_1.id
            assert sink_relationship.sink_id == germplasm_2.id
        except StopAsyncIteration:
            raise ValueError("Sink relationship not found")

@pytest.mark.asyncio(loop_scope="session")
async def test_read_access_control(
        uow_factory,
        germplasm_build_context
):
    user_id_1 = germplasm_build_context['user_id_1']
    team_id = germplasm_build_context['team_id']
    user_id_2 = germplasm_build_context['user_id_2']
    germplasm_input = GermplasmBuilder.germplasm_input()
    async with uow_factory.get_uow(user_id=user_id_1) as uow:
        germplasm_entry = await uow.germplasm.create_entry(germplasm_input)
        await uow.commit()

    # verify the created germplasm is not accessible or discoverable to anonymous users
    async with uow_factory.get_uow() as uow:
        no_germplasm = await uow.germplasm.get_entry(germplasm_entry.id)
        assert no_germplasm is None
        with pytest.raises(StopAsyncIteration):
            await anext(uow.germplasm.get_entries(names=[germplasm_entry.name]))
        async for g in uow.germplasm.get_entries():
            if g.name == germplasm_entry.name:
                raise UnauthorisedOperationError("Public can see a private germplasm entry by get all")


    # verify the created germplasm is redacted when get by ID and not discoverable by name to registered users
    async with uow_factory.get_uow(user_id=user_id_2) as uow:
        redacted_germplasm = await uow.germplasm.get_entry(germplasm_entry.id)
        assert redacted_germplasm.name == redacted_germplasm.redacted_str
        with pytest.raises(StopAsyncIteration):
            await anext(uow.germplasm.get_entries(names=[germplasm_entry.name]))
        async for g in uow.germplasm.get_entries():
            if g.id == germplasm_entry.id:
                assert g.name == g.redacted_str
            if g.name == germplasm_entry.name:
                raise UnauthorisedOperationError("Registered users can see a private germplasm entry by get all")

    # Change release to registered as first user (has both write and admin affiliation)
    async with uow_factory.get_uow(user_id=user_id_1) as uow:
        germplasm_entry = await uow.germplasm.get_entry(germplasm_entry.id)
        assert germplasm_entry
        await uow.controls.set_controls(
            models=[germplasm_entry],
            control_teams={team_id},
            release=ReadRelease.REGISTERED
        )
        await uow.commit()

    # verify the created germplasm is still not accessible or discoverable to anonymous users
    async with uow_factory.get_uow() as uow:
        no_germplasm = await uow.germplasm.get_entry(germplasm_entry.id)
        assert no_germplasm is None
        with pytest.raises(StopAsyncIteration):
            await anext(uow.germplasm.get_entries(names=[germplasm_entry.name]))
        async for g in uow.germplasm.get_entries():
            if g.name == germplasm_entry.name:
                raise UnauthorisedOperationError("Public can see a private germplasm entry by get all")

    # verify the created germplasm is now visible when get by ID and discoverable by name to registered users
    async with uow_factory.get_uow(user_id=user_id_2) as uow:
        germplasm_entry = await uow.germplasm.get_entry(germplasm_entry.id)
        assert germplasm_entry
        assert germplasm_entry.name == germplasm_input.name
        germplasm_entry = await anext(uow.germplasm.get_entries(names=[germplasm_entry.name]))
        assert germplasm_entry.name == germplasm_input.name
        async for g in uow.germplasm.get_entries():
            if g.id == germplasm_entry.id:
                assert g.name == germplasm_input.name
                break
        else:
            raise ValueError("Registered user cannot see germplasm with release registered by get all")

    # release to public as first user (has both write and admin affiliation)
    async with uow_factory.get_uow(user_id=user_id_1) as uow:
        germplasm_entry = await uow.germplasm.get_entry(germplasm_entry.id)
        assert germplasm_entry
        await uow.controls.set_controls(
            models=[germplasm_entry],
            control_teams={team_id},
            release=ReadRelease.PUBLIC
        )
        await uow.commit()

    # verify the created germplasm is now accessible and discoverable to anonymous users
    async with uow_factory.get_uow() as uow:
        germplasm_entry = await uow.germplasm.get_entry(germplasm_entry.id)
        assert germplasm_entry.name == germplasm_input.name
        germplasm_entry = await anext(uow.germplasm.get_entries(names=[germplasm_entry.name]))
        assert germplasm_entry.name == germplasm_input.name
        async for g in uow.germplasm.get_entries():
            if g.id == germplasm_entry.id:
                assert g.name == germplasm_input.name
                break
        else:
            raise ValueError("Anonymous user cannot see germplasm with release public by get all")

    # verify the created germplasm is still visible when get by ID and discoverable by name to registered users
    async with uow_factory.get_uow(user_id=user_id_2) as uow:
        germplasm_entry = await uow.germplasm.get_entry(germplasm_entry.id)
        assert germplasm_entry
        assert germplasm_entry.name == germplasm_input.name
        germplasm_entry = await anext(uow.germplasm.get_entries(names=[germplasm_entry.name]))
        assert germplasm_entry.name == germplasm_input.name
        async for g in uow.germplasm.get_entries():
            if g.id == germplasm_entry.id:
                assert g.name == germplasm_input.name
                break
        else:
            raise ValueError("Registered user cannot see germplasm with release public by get all")

@pytest.mark.asyncio(loop_scope="session")
async def test_edit_name_access_control(
        uow_factory,
        germplasm_build_context,
        lorem_text_generator
):
    user_id_1 = germplasm_build_context['user_id_1']
    team_id = germplasm_build_context['team_id']
    user_id_2 = germplasm_build_context['user_id_2']
    germplasm_input = GermplasmBuilder.germplasm_input()
    new_name = lorem_text_generator.new_text(10)
    async with uow_factory.get_uow(user_id=user_id_1) as uow:
        germplasm_entry = await uow.germplasm.create_entry(germplasm_input)
        await uow.controls.set_controls(
            models=[germplasm_entry],
            control_teams={team_id},
            release=ReadRelease.PUBLIC
        )
        await uow.commit()

    # verify the created germplasm can be modified by user with write access
    async with uow_factory.get_uow(user_id=user_id_1) as uow:
        germplasm_entry = await uow.germplasm.get_entry(germplasm_entry.id)
        assert germplasm_entry
        germplasm_entry.name = new_name
        await uow.germplasm.update_entry(germplasm_entry)
        await uow.commit()

    async with uow_factory.get_uow(user_id=user_id_1) as uow:
        germplasm_entry = await uow.germplasm.get_entry(germplasm_entry.id)
        assert germplasm_entry
        assert germplasm_entry.name == new_name

    # verify the created germplasm is protected from changes by anonymous users
    with pytest.raises(UnauthorisedOperationError) as e:
        async with uow_factory.get_uow() as uow:
            fraudulent_germplasm_entry = GermplasmStored(id=germplasm_entry.id, name=lorem_text_generator.new_text(10))
            await uow.germplasm.update_entry(fraudulent_germplasm_entry)
            await uow.commit()

    # verify the created germplasm is protected from changes by registered users that don't have write access
    with pytest.raises(UnauthorisedOperationError) as e:
        async with uow_factory.get_uow(user_id=user_id_2) as uow:
            germplasm_entry = await uow.germplasm.get_entry(germplasm_entry.id)
            assert germplasm_entry
            germplasm_entry.name = lorem_text_generator.new_text(10)
            await uow.germplasm.update_entry(germplasm_entry)
            await uow.commit()

    # authorise write access to user_2
    await AuthorisationManager(uow_factory).authorise_affiliation(
        agent_id=user_id_1,
        user_id=user_id_2,
        team_id=team_id,
        access=Access.CURATE
    )
    await AuthorisationManager(uow_factory).authorise_affiliation(
        agent_id=user_id_1,
        user_id=user_id_2,
        team_id=team_id,
        access=Access.READ
    )
    # validate write now available to user_2
    async with uow_factory.get_uow(user_id=user_id_2) as uow:
        germplasm_entry = await uow.germplasm.get_entry(germplasm_entry.id)
        assert germplasm_entry
        second_name = lorem_text_generator.new_text(10)
        germplasm_entry.name = second_name
        await uow.germplasm.update_entry(germplasm_entry)
        await uow.commit()

    async with uow_factory.get_uow(user_id=user_id_2) as uow:
        germplasm_entry = await uow.germplasm.get_entry(germplasm_entry.id)
        assert germplasm_entry
        assert germplasm_entry.name == second_name


@pytest.mark.asyncio(loop_scope="session")
async def test_get_descendants_and_ancestors(
        uow_factory,
        germplasm_build_context
):
    # todo test access control changes in ancestor/descendant graph
    """Test retrieving descendants and ancestors through the service."""
    user_id = germplasm_build_context['user_id']

    crop_id = await GermplasmBuilder(uow_factory).germplasm(user_id=user_id)
    group_id = await GermplasmBuilder(uow_factory).germplasm(user_id=user_id)
    variety_id = await GermplasmBuilder(uow_factory).germplasm(user_id=user_id)
    accession_id = await GermplasmBuilder(uow_factory).germplasm(user_id=user_id)

    async with uow_factory.get_uow(user_id=user_id) as uow:
        await uow.germplasm.create_relationship(GermplasmRelationship(source_id=crop_id, sink_id=group_id))
        await uow.germplasm.create_relationship(GermplasmRelationship(source_id=group_id, sink_id=variety_id))
        await uow.germplasm.create_relationship(GermplasmRelationship(source_id=variety_id, sink_id=accession_id))
        await uow.commit()

    async with uow_factory.get_uow(user_id=user_id) as uow:
        crop_descendants = await uow.germplasm.get_descendant_ids(crop_id)
        assert crop_descendants.index(variety_id) < crop_descendants.index(accession_id)
        accession_ancestors = await uow.germplasm.get_ancestor_ids(accession_id)
        assert accession_ancestors.index(variety_id) < accession_ancestors.index(crop_id)



