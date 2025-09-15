import pytest
import pytest_asyncio

from src.breedgraph.domain.model.arrangements import Arrangement, LayoutInput, LayoutStored
from src.breedgraph.domain.model.ontology import AxisType
from src.breedgraph.domain.model.controls import Access

from src.breedgraph.adapters.neo4j.repositories import Neo4jArrangementsRepository

@pytest.mark.usefixtures("session_database")
@pytest.mark.asyncio(scope="session")
async def test_create_row_arrangement(
        uncommitted_neo4j_tx,
        neo4j_access_control_service,
        stored_account,
        stored_organisation,
        read_model,
        row_layout_type,
        field_location
):
    repo = Neo4jArrangementsRepository(
        uncommitted_neo4j_tx,
        access_control_service=neo4j_access_control_service,
        user_id=stored_account.user.id,
        access_teams={
            Access.READ: {stored_organisation.root.id},
            Access.WRITE: {stored_organisation.root.id},
        }
    )
    row_layout_input = LayoutInput(type=row_layout_type.id, location=field_location.id, axes=[AxisType.ORDINAL])
    stored: Arrangement = await repo.create(row_layout_input)
    retrieved = await repo.get(layout_id = stored.root.id)
    assert stored.root == retrieved.root
    async for l in repo.get_all():
        if stored.root.id == l.root.id:
            break
    else:
        raise AssertionError("couldn't find stored arrangement by get all")

@pytest.mark.usefixtures("session_database")
@pytest.mark.asyncio(scope="session")
async def test_extend_row_with_grid(
        uncommitted_neo4j_tx,
        neo4j_access_control_service,
        stored_account,
        stored_organisation,
        grid_layout_type
):
    repo = Neo4jArrangementsRepository(
        uncommitted_neo4j_tx,
        access_control_service=neo4j_access_control_service,
        user_id=stored_account.user.id,
        access_teams={
            Access.READ: {stored_organisation.root.id},
            Access.WRITE: {stored_organisation.root.id},
        }
    )
    arrangement = await anext(repo.get_all())
    grid_layout_input_1 = LayoutInput(name = "layout 1", type=grid_layout_type.id, location=arrangement.root.location)
    grid_layout_input_2 = LayoutInput(name = "layout 2", type=grid_layout_type.id)
    arrangement.add_layout(layout=grid_layout_input_1, parent_id=arrangement.root.id, position=["1"])
    arrangement.add_layout(layout=grid_layout_input_2, parent_id=arrangement.root.id, position=["2"])
    await repo.update_seen()
    arrangement = await repo.get()
    found = 0
    for k, v in arrangement.get_sinks(arrangement.root.id).items():
        if v.name in [grid_layout_input_1.name, grid_layout_input_2.name]:
            found += 1
    assert found == 2
