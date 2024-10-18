import pytest

from src.breedgraph.domain.model.controls import ReadRelease
from src.breedgraph.adapters.repositories.regions import Neo4jRegionsRepository
from src.breedgraph.domain.model.regions import LocationInput

#@pytest.mark.usefixtures("session_database")
@pytest.mark.asyncio(scope="session")
async def test_extend_region(
        ontology, state_type,
        lorem_text_generator,
        regions_repo,
        example_region
):
    region = await regions_repo.get()
    county_input = LocationInput(
        type=state_type.id,
        name=lorem_text_generator.new_text()
    )
    region.add_location(location=county_input, parent_id=region.root.id)
    await regions_repo.update_seen()
    region = await regions_repo.get()
    added_region_id = region.get_location(county_input.name).id
    assert added_region_id in region.get_sinks(region.root.id)

@pytest.mark.asyncio(scope="session")
async def test_make_sub_region_private(
        neo4j_tx,
        stored_account,
        second_account,
        stored_organisation,
        ontology, field_type,
        regions_repo
):
    region = await regions_repo.get()
    county_id = list(region.get_sinks(region.root.id).keys())[0]
    county = region.get_location(county_id)
    county.controller.set_release(release=ReadRelease.PRIVATE, team_id=stored_organisation.root.id)
    await regions_repo.update_seen()
    region = await regions_repo.get()
    county = region.get_location(county_id)
    assert county.controller.release == ReadRelease.PRIVATE
    registered_repo = Neo4jRegionsRepository(
        neo4j_tx,
        user_id=stored_account.user.id
    )
    region = await registered_repo.get()
    assert county_id not in region.entries
