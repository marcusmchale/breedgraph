import pytest
import pytest_asyncio

from src.breedgraph.custom_exceptions import UnauthorisedOperationError
from src.breedgraph.domain.model.blocks import UnitInput, UnitStored, Block,  Position

from src.breedgraph.adapters.repositories.blocks import Neo4jBlocksRepository


@pytest.mark.asyncio(scope="session")
async def test_update(
        blocks_repo,
        neo4j_tx, stored_account, stored_organisation,
        example_variety,
        tree_subject,
        field_location,
        example_arrangement
):
    stored_block = await blocks_repo.get()
    stored_block.root.name = "New name"
    with pytest.raises(UnauthorisedOperationError):
        # should fail without curate permission
        await blocks_repo.update_seen()

    blocks_repo = Neo4jBlocksRepository(
        neo4j_tx,
        user_id=stored_account.user.id,
        read_teams=[stored_organisation.root.id],
        write_teams=[stored_organisation.root.id],
        curate_teams=[stored_organisation.root.id]
    )
    stored_block = await blocks_repo.get()
    stored_block.root.name = "New name this time"
    await blocks_repo.update_seen()

    retrieved = await blocks_repo.get(unit_id=stored_block.root.id)
    assert retrieved.root.name == "New name this time"
