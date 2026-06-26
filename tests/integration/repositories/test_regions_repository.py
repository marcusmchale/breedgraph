import pytest

from breedgraph.domain.model.controls import ReadRelease
from breedgraph.domain.model.regions import LocationInput, LocationStored
from breedgraph.custom_exceptions import IdentityExistsError

from tests.scenarios import RegionBuilder


@pytest.mark.asyncio(loop_scope="session")
async def test_create_region(
        uow_factory,
        state_store,
        region_build_context
):
    user_id = region_build_context['user_id']
    async with uow_factory.get_uow(user_id=user_id) as uow:
        region = None
        count = 0
        async for country in state_store.get_countries():
            count += 1
            if isinstance(country, LocationStored):
                pass
            else:
                try:
                    region = await uow.repositories.regions.create(country)
                    break
                except IdentityExistsError:
                    pass
        if count == 0:
            raise ValueError("No countries were found in read model to create a test region")
        elif region is None:
            raise ValueError("All stored countries are already created!")
        await uow.commit()

    async with uow_factory.get_uow(user_id=user_id) as uow:
        region = await uow.repositories.regions.get()
        assert region
        assert region.root.name == country.name

@pytest.mark.asyncio(loop_scope="session")
async def test_extend_region(
        uow_factory,
        state_store,
        region_build_context,
        lorem_text_generator
):
    user_id = region_build_context['user_id']
    state_type_id = region_build_context['ontology_location_state']
    field_type_id = region_build_context['ontology_location_field']
    async with uow_factory.get_uow(user_id=user_id) as uow:
        region = await RegionBuilder(uow_factory=uow_factory, state_store=state_store).region_from_country(uow)
        temp_field_id = region.add_location(
            LocationInput(
                name=lorem_text_generator.new_text(10),
                type=state_type_id
            ),
            parent_id=region.get_root_id()
        )
        region.add_location(
            LocationInput(
                name=lorem_text_generator.new_text(10),
                type=field_type_id
            ),
            parent_id=temp_field_id
        )
        await uow.commit()

    async with uow_factory.get_uow(user_id=user_id) as uow:
        region = await uow.repositories.regions.get(location_id=region.root.id)
        assert region.size == 3


@pytest.mark.asyncio(loop_scope="session")
async def test_make_location_visible_to_registered(
        uow_factory,
        state_store,
        region_build_context,
        lorem_text_generator
):
    user_id_1 = region_build_context['user_id_1']
    user_id_2 = region_build_context['user_id_2']
    team_id = region_build_context['team_id']
    state_type_id = region_build_context['ontology_location_state']
    field_type_id = region_build_context['ontology_location_field']
    lab_type_id = region_build_context['ontology_location_lab']
    region_ids = await RegionBuilder(uow_factory, state_store).region(
        user_id=user_id_1,
        ontology_location_state=state_type_id,
        ontology_location_field=field_type_id,
        ontology_location_lab=lab_type_id
    )
    # Ensure registered can't see field in aggregate
    async with uow_factory.get_uow(user_id=user_id_2) as uow:
        region = await uow.repositories.regions.get(location_id=region_ids['location_country_id'])
        assert region.size == 1

    # Change access to registered
    async with uow_factory.get_uow(user_id=user_id_1) as uow:
        region = await uow.repositories.regions.get(location_id=region_ids['location_country_id'])
        assert region
        assert region.size == 4
        field = region.get_location(region_ids['location_field_id'])
        assert field
        await uow.controls.set_controls(
            models=[field],
            control_teams={team_id},
            release=ReadRelease.REGISTERED
        )
        await uow.commit()

    # Ensure registered now have visibility of a redacted graph (only root and field)
    async with uow_factory.get_uow(user_id=user_id_2) as uow:
        region = await uow.repositories.regions.get(location_id=region_ids['location_field_id'])
        assert region.size == 2
