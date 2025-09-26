import pytest

from src.breedgraph.domain.model.controls import ReadRelease
from src.breedgraph.adapters.neo4j.repositories import Neo4jRegionsRepository
from src.breedgraph.domain.model.regions import LocationInput

@pytest.mark.usefixtures("session_database")
@pytest.mark.asyncio(scope="session")
async def test_extend_region(
        state_type,
        lorem_text_generator,
        regions_repo,
        example_region
):
    region = example_region
    county_input = LocationInput(
        type=state_type.id,
        name=lorem_text_generator.new_text()
    )
    region.add_location(location=county_input, parent_id=region.root.id)
    await regions_repo.update_seen()
    region = await regions_repo.get(location_id=region.root.id)
    added_region_id = region.get_location(county_input.name).id
    assert added_region_id in region.get_sinks(region.root.id)

@pytest.mark.asyncio(scope="session")
async def test_make_sub_region_private(
        uncommitted_neo4j_tx,
        neo4j_access_control_service,
        first_unstored_account,
        second_unstored_account,
        first_unstored_organisation,
        field_type,
        regions_repo,
        example_region
):
    region = example_region
    county_id = list(region.get_sinks(region.root.id).keys())[0]
    county = region.get_location(county_id)
    await neo4j_access_control_service.initialize_user_context(user_id = first_unstored_account.user.id)
    await regions_repo.set_entity_access_controls(
        county,
        control_teams= {first_unstored_organisation.root.id},
        release=ReadRelease.PRIVATE
    )
    await regions_repo.update_seen()

    await neo4j_access_control_service.initialize_user_context(user_id=second_unstored_account.user.id)
    registered_repo = Neo4jRegionsRepository(
        uncommitted_neo4j_tx,
        access_control_service=neo4j_access_control_service
    )
    region = await registered_repo.get(location_id = region.root.id)
    assert county_id not in region.entries

