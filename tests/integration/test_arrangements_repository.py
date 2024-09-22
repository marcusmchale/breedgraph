import pytest
import pytest_asyncio

from src.breedgraph.domain.model.arrangements import Arrangement, LayoutInput, LayoutStored

from src.breedgraph.adapters.repositories.arrangements import Neo4jArrangementsRepository


@pytest.mark.asyncio(scope="session")
async def test_create_row_arrangement(
        neo4j_tx,
        stored_account,
        stored_organisation,
        read_model,
        row_layout_type,
        field_location
):
    repo = Neo4jArrangementsRepository(
        neo4j_tx,
        user_id=stored_account.user.id,
        read_teams=[stored_organisation.root.id],
        write_teams=[stored_organisation.root.id]
    )

    row_layout_input = LayoutInput(type=row_layout_type.id, location=field_location.id)

    stored: Arrangement = await repo.create(row_layout_input)
    retrieved = await repo.get(layout_id = stored.root.id)

    assert stored.root == retrieved.root
    async for l in repo.get_all():
        if stored.root.id == l.root.id:
            break
    else:
        raise AssertionError("couldn't find stored arrangement by get all")

@pytest.mark.asyncio(scope="session")
async def test_extend_row_with_grid(
        neo4j_tx,
        stored_account,
        stored_organisation,
        grid_layout_type,
        field_location
):
    repo = Neo4jArrangementsRepository(
        neo4j_tx,
        user_id=stored_account.user.id,
        read_teams=[stored_organisation.root.id],
        write_teams=[stored_organisation.root.id]
    )
    arrangement = await anext(repo.get_all())
    grid_layout_input_1 = LayoutInput(type=grid_layout_type.id, location=field_location.id)
    grid_layout_input_2 = LayoutInput(type=grid_layout_type.id, location=field_location.id)

    arrangement.add_layout(layout=grid_layout_input_1, parent_id=arrangement.root.id, position=1)
    arrangement.add_layout(layout=grid_layout_input_2, parent_id=arrangement.root.id, position=2)
    await repo.update_seen()
    arrangement = await repo.get()
    assert len(arrangement.get_sinks(arrangement.root.id)) == 2

#@pytest.mark.asyncio(scope="session")
#async def test_extend_grid_with_units():
# TODO create units repository
#
