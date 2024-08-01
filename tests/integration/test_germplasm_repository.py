import pytest
import pytest_asyncio

from src.breedgraph.domain.model.germplasm import (
    Germplasm,
    GermplasmSourceType, Reproduction,
    GermplasmEntry, GermplasmEntryInput, GermplasmEntryStored
)
from src.breedgraph.domain.model.controls import Control, Controller, ReadRelease
from src.breedgraph.adapters.repositories.germplasms import Neo4jGermplasmRepository


@pytest_asyncio.fixture
def first_entry_input(lorem_text_generator, stored_organisation):
    return GermplasmEntryInput(
        name=lorem_text_generator.new_text(10),
        synonyms=[lorem_text_generator.new_text(5)],
        controller=Controller(controls={stored_organisation.root.id:Control(release=ReadRelease.PRIVATE)})
    )

@pytest.mark.asyncio(scope="session")
async def test_create_and_get(neo4j_tx, first_entry_input, stored_account, stored_organisation):
    repo = Neo4jGermplasmRepository(
        neo4j_tx,
        user_id=stored_account.user.id,
        read_teams=[stored_organisation.root.id]
    )
    assert await repo.get() is None
    stored_germplasm = await repo.create(first_entry_input)
    assert stored_germplasm.root.name == first_entry_input.name
    assert stored_germplasm.root.id > 0
    stored_germplasm = await repo.get(entry_id=stored_germplasm.root.id)
    assert stored_germplasm.root.name == first_entry_input.name
    assert stored_germplasm.root.id > 0
    stored_germplasm = await anext(repo.get_all())
    assert stored_germplasm.root.name == first_entry_input.name
    assert stored_germplasm.root.id > 0

@pytest.mark.asyncio(scope="session")
async def test_get_without_read(neo4j_tx, first_entry_input, stored_account, stored_organisation):
    repo = Neo4jGermplasmRepository(
        neo4j_tx,
        user_id=stored_account.user.id
    )
    stored_germplasm = await repo.get()
    assert stored_germplasm.root.name == Germplasm._redacted_str
    assert stored_germplasm.root.id > 0
    stored_germplasm = await anext(repo.get_all())
    assert stored_germplasm.root.name == Germplasm._redacted_str
    assert stored_germplasm.root.id > 0
