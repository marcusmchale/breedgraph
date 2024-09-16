import pytest
import pytest_asyncio

from src.breedgraph.domain.model.blocks import UnitInput, UnitStored, Block,  Position

from src.breedgraph.adapters.repositories.blocks import Neo4jBlocksRepository

@pytest.mark.asyncio(scope="session")
async def test_create_and_get_succeeds(
        neo4j_tx,
        stored_account,
        stored_organisation,
        example_variety,
        tree_subject,
        field_location,
        example_arrangement
):
    repo = Neo4jBlocksRepository(
        neo4j_tx,
        user_id=stored_account.user.id,
        read_teams=[stored_organisation.root.id],
        write_teams=[stored_organisation.root.id]
    )
    new_unit = UnitInput(
        subject=tree_subject.id,
        name="First Tree",
        synonyms=['1st tree'],
        description="The first tree planted",
        germplasm=example_variety.id,
        positions=[
            Position(
                location=field_location.id,
                layout=example_arrangement.root.id,
                coordinates=[1,1],
                start="2010"
            )
        ]
    )
    stored_block = await repo.create(new_unit)
    import pdb; pdb.set_trace()

