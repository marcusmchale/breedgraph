import pytest

@pytest.mark.asyncio(scope="session")
async def test_update(
        blocks_repo,
        tree_block,
        example_variety,
        tree_subject,
        field_location,
        example_arrangement
):
    tree_block.root.name = "New name"

    stored_block = await blocks_repo.get()
    stored_block.root.name = "New name this time"
    await blocks_repo.update_seen()

    retrieved = await blocks_repo.get(unit_id=stored_block.root.id)
    assert retrieved.root.name == "New name this time"
