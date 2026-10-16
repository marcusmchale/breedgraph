import pytest

from breedgraph.domain.model.controls import ReadRelease
from breedgraph.domain.model.location_trees import LocationInput, LocationStored
from breedgraph.custom_exceptions import IdentityExistsError

from tests.breedgraph.scenarios import LocationTreeBuilder


@pytest.mark.asyncio(loop_scope="session")
async def test_create_location_tree(
        uow_factory,
        state_store,
        location_tree_build_context
):
    user_id = location_tree_build_context['user_id']
    async with uow_factory.get_uow(user_id=user_id, write_team=location_tree_build_context['team_id']) as uow:
        location_tree = None
        count = 0
        async for country in state_store.get_countries():
            count += 1
            if isinstance(country, LocationStored):
                pass
            else:
                try:
                    location_tree = await uow.repositories.location_trees.create(country)
                    break
                except IdentityExistsError:
                    pass
        if count == 0:
            raise ValueError("No countries were found in read model to create a test location tree")
        elif location_tree is None:
            raise ValueError("All stored countries are already created!")
        await uow.commit()

    async with uow_factory.get_uow(user_id=user_id) as uow:
        location_tree = await uow.repositories.location_trees.get()
        assert location_tree
        assert location_tree.root.name == country.name

@pytest.mark.asyncio(loop_scope="session")
async def test_extend_location_tree(
        uow_factory,
        state_store,
        location_tree_build_context,
        lorem_text_generator
):
    user_id = location_tree_build_context['user_id']
    state_type_id = location_tree_build_context['ontology_location_state']
    field_type_id = location_tree_build_context['ontology_location_field']
    async with uow_factory.get_uow(user_id=user_id, write_team=location_tree_build_context['team_id']) as uow:
        location_tree = await LocationTreeBuilder(uow_factory=uow_factory, state_store=state_store).location_tree_from_country(uow)
        temp_field_id = location_tree.add_location(
            LocationInput(
                name=lorem_text_generator.new_text(10),
                type=state_type_id
            ),
            parent_id=location_tree.get_root_id()
        )
        location_tree.add_location(
            LocationInput(
                name=lorem_text_generator.new_text(10),
                type=field_type_id
            ),
            parent_id=temp_field_id
        )
        await uow.commit()

    async with uow_factory.get_uow(user_id=user_id) as uow:
        location_tree = await uow.repositories.location_trees.get(location_id=location_tree.root.id)
        assert location_tree.size == 3


@pytest.mark.asyncio(loop_scope="session")
async def test_locations_within_location_trees_may_share_names(
        uow_factory,
        state_store,
        location_tree_build_context
):
    """Only roots must be unique. Locations added in one commit are linked to their parents after all are created."""
    user_id = location_tree_build_context['user_id']
    state_type_id = location_tree_build_context['ontology_location_state']
    field_type_id = location_tree_build_context['ontology_location_field']
    async with uow_factory.get_uow(user_id=user_id, write_team=location_tree_build_context['team_id']) as uow:
        location_tree = await LocationTreeBuilder(uow_factory=uow_factory, state_store=state_store).location_tree_from_country(uow)
        for state_name in ("State A", "State B"):
            state_id = location_tree.add_location(LocationInput(name=state_name, type=state_type_id), parent_id=location_tree.get_root_id())
            location_tree.add_location(LocationInput(name="Station (1)", type=field_type_id), parent_id=state_id)
        await uow.commit()

    async with uow_factory.get_uow(user_id=user_id) as uow:
        location_tree = await uow.repositories.location_trees.get(location_id=location_tree.root.id)
        assert [location.name for location in location_tree.yield_locations_by_type(field_type_id)] == ["Station (1)"] * 2


@pytest.mark.asyncio(loop_scope="session")
async def test_make_location_visible_to_registered(
        uow_factory,
        state_store,
        location_tree_build_context,
        lorem_text_generator
):
    user_id_1 = location_tree_build_context['user_id_1']
    user_id_2 = location_tree_build_context['user_id_2']
    team_id = location_tree_build_context['team_id']
    state_type_id = location_tree_build_context['ontology_location_state']
    field_type_id = location_tree_build_context['ontology_location_field']
    lab_type_id = location_tree_build_context['ontology_location_lab']
    location_tree_ids = await LocationTreeBuilder(uow_factory, state_store).location_tree(
        user_id=user_id_1,
        team_id=team_id,
        ontology_location_state=state_type_id,
        ontology_location_field=field_type_id,
        ontology_location_lab=lab_type_id
    )
    # Ensure registered can't see field in aggregate: the repository returns it whole, redaction is explicit
    async with uow_factory.get_uow(user_id=user_id_2) as uow:
        location_tree = await uow.repositories.location_trees.get(location_id=location_tree_ids['location_country_id'])
        assert location_tree.size == 4
        assert (await uow.repositories.location_trees.redacted(location_tree)).size == 1

    # Change access to registered
    async with uow_factory.get_uow(user_id=user_id_1) as uow:
        location_tree = await uow.repositories.location_trees.get(location_id=location_tree_ids['location_country_id'])
        assert location_tree
        assert location_tree.size == 4
        field = location_tree.get_location(location_tree_ids['location_field_id'])
        assert field
        await uow.controls.set_controls(
            models=[field],
            control_teams={team_id},
            release=ReadRelease.REGISTERED
        )
        await uow.commit()

    # Ensure registered now have visibility of a redacted graph (only root and field)
    async with uow_factory.get_uow(user_id=user_id_2) as uow:
        location_tree = await uow.repositories.location_trees.get(location_id=location_tree_ids['location_field_id'])
        assert (await uow.repositories.location_trees.redacted(location_tree)).size == 2
