import pytest
import pytest_asyncio
import numpy as np

from src.breedgraph.custom_exceptions import IllegalOperationError
from src.breedgraph.domain.model.germplasm import (
    Germplasm, GermplasmEntryInput, GermplasmEntry
)
from src.breedgraph.domain.model.controls import Access
from src.breedgraph.adapters.repositories.germplasms import Neo4jGermplasmRepository, GermplasmSourceType

def get_entry_input(lorem_text_generator):
    return GermplasmEntryInput(
        name=lorem_text_generator.new_text(10),
        synonyms=[lorem_text_generator.new_text(5)]
    )

@pytest_asyncio.fixture
def first_entry_input(lorem_text_generator):
    return get_entry_input(lorem_text_generator)


@pytest.mark.asyncio(scope="session")
async def test_create_fails_without_user_or_write_teams(
        neo4j_uow,
        test_controllers_service,
        first_entry_input,
        stored_account,
        lorem_text_generator,
        stored_organisation
):
    async with neo4j_uow.get_repositories() as uow:
        repo = Neo4jGermplasmRepository(
            uow.tx,
            controllers_service=test_controllers_service,
            access_teams={
                Access.WRITE: {stored_organisation.root.id}
            }
        )
        new_entry = get_entry_input(lorem_text_generator)
        with pytest.raises(IllegalOperationError):
            await repo.create(new_entry)

    async with neo4j_uow.get_repositories() as uow:
        repo = Neo4jGermplasmRepository(
            uow.tx,
            controllers_service=test_controllers_service,
            user_id=stored_account.user.id
        )
        new_entry = get_entry_input(lorem_text_generator)
        with pytest.raises(IllegalOperationError):
            await repo.create(new_entry)

    async with neo4j_uow.get_repositories() as uow:
        repo = Neo4jGermplasmRepository(
            uow.tx,
            controllers_service = test_controllers_service,
        )
        new_entry = get_entry_input(lorem_text_generator)
        with pytest.raises(IllegalOperationError):
            await repo.create(new_entry)


@pytest.mark.asyncio(scope="session")
async def test_create_entry(
        neo4j_tx,
        test_controllers_service,
        stored_account,
        first_entry_input,
        lorem_text_generator,
        stored_organisation,
        example_germplasm
):
    repo = Neo4jGermplasmRepository(
        neo4j_tx,
        controllers_service=test_controllers_service,
        user_id=stored_account.user.id,
        access_teams={
            Access.READ: {stored_organisation.root.id},
            Access.WRITE: {stored_organisation.root.id}
        }
    )
    stored_germplasm = await repo.get()
    new_entry = get_entry_input(lorem_text_generator)
    stored_germplasm.add_entry(
        new_entry,
        sources = {stored_germplasm.root.id: {'type': GermplasmSourceType.SEED}}
    )
    await repo.update_seen()
    for key, value in stored_germplasm.get_sink_edges(stored_germplasm.get_root_id()).items():

        if value.get('type') == GermplasmSourceType.SEED:
            break
    else:
        raise ValueError("Couldn't find the seed type sink")

    new_entry2 = get_entry_input(lorem_text_generator)
    stored_germplasm.add_entry(
        new_entry2,
        sources = {stored_germplasm.root.id: None}
    )
    await repo.update_seen()
    for key, value in stored_germplasm.get_sink_edges(stored_germplasm.get_root_id()).items():
        if value.get('type') == GermplasmSourceType.UNKNOWN:
            break
    else:
        raise ValueError("Couldn't find the unknown type sink")

@pytest.mark.asyncio(scope="session")
async def test_get_without_read_returns_redacted(
        neo4j_tx,
        test_controllers_service,
        first_entry_input,
        stored_account,
        stored_organisation
):
    repo = Neo4jGermplasmRepository(
        neo4j_tx,
        controllers_service=test_controllers_service,
        user_id=stored_account.user.id
    )
    stored_germplasm = await repo.get()
    assert stored_germplasm.root.name == Germplasm._redacted_str
    assert stored_germplasm.root.id > 0
    stored_germplasm = await anext(repo.get_all())
    assert stored_germplasm.root.name == Germplasm._redacted_str
    assert stored_germplasm.root.id > 0

@pytest.mark.asyncio(scope="session")
async def test_insert_root(
        neo4j_tx,
        test_controllers_service,
        stored_account,
        first_entry_input,
        lorem_text_generator,
        stored_organisation
):
    repo = Neo4jGermplasmRepository(
        neo4j_tx,
        controllers_service=test_controllers_service,
        user_id=stored_account.user.id,
        access_teams={
            Access.READ: {stored_organisation.root.id},
            Access.WRITE: {stored_organisation.root.id},
            Access.CURATE: {stored_organisation.root.id}
        }
    )
    stored_germplasm = await repo.get()
    root_name = stored_germplasm.root.name
    root_id = stored_germplasm.get_root_id()
    new_root = get_entry_input(lorem_text_generator)
    stored_germplasm.insert_root(new_root)
    await repo.update_seen()
    repo = Neo4jGermplasmRepository(
        neo4j_tx,
        controllers_service=test_controllers_service,
        user_id=stored_account.user.id,
        access_teams={
            Access.READ: {stored_organisation.root.id},
            Access.WRITE: {stored_organisation.root.id}
        }
    )
    stored_germplasm = await repo.get()
    assert stored_germplasm.root.name != root_name
    assert root_id in stored_germplasm.get_descendants(stored_germplasm.get_root_id())


@pytest.mark.asyncio(scope="session")
async def test_delete_entry(
        neo4j_tx,
        test_controllers_service,
        stored_account,
        first_entry_input,
        lorem_text_generator,
        stored_organisation
):
    repo = Neo4jGermplasmRepository(
        neo4j_tx,
        controllers_service=test_controllers_service,
        user_id=stored_account.user.id,
        access_teams={
            Access.READ: {stored_organisation.root.id},
            Access.CURATE: {stored_organisation.root.id}
        }
    )
    stored_germplasm = await repo.get()
    to_remove = list(stored_germplasm.get_descendants(stored_germplasm.root.id))[-1]
    stored_germplasm.remove_entry(to_remove)
    await repo.update_seen()
    stored_germplasm = await repo.get()
    assert to_remove not in stored_germplasm.entries

@pytest.mark.asyncio(scope="session")
async def test_edit_entry(
        neo4j_tx,
        test_controllers_service,
        stored_account,
        first_entry_input,
        lorem_text_generator,
        stored_organisation
):
    repo = Neo4jGermplasmRepository(
        neo4j_tx,
        controllers_service=test_controllers_service,
        user_id=stored_account.user.id,
        access_teams={
            Access.READ: {stored_organisation.root.id},
            Access.WRITE: {stored_organisation.root.id},
            Access.CURATE: {stored_organisation.root.id}
        }
    )
    stored_germplasm = await repo.get()
    old_root_name = stored_germplasm.root.name
    new_root_name = lorem_text_generator.new_text(10)
    stored_germplasm.root.name = new_root_name
    await repo.update_seen()
    stored_germplasm = await repo.get()
    assert stored_germplasm.root.name != old_root_name

@pytest.mark.asyncio(scope="session")
async def test_time_attribute(
        neo4j_tx,
        test_controllers_service,
        stored_account,
        first_entry_input,
        lorem_text_generator,
        stored_organisation
):
    repo = Neo4jGermplasmRepository(
        neo4j_tx,
        controllers_service=test_controllers_service,
        user_id=stored_account.user.id,
        access_teams={
            Access.READ: {stored_organisation.root.id},
            Access.WRITE: {stored_organisation.root.id},
            Access.CURATE: {stored_organisation.root.id}
        }
    )
    time_str = '2014'
    entry_input = GermplasmEntry(name='asdf', time=time_str)
    germplasm = await repo.create(entry_input)
    await repo.update_seen()
    stored_germplasm = await repo.get(entry_id=germplasm.get_root_id())
    assert stored_germplasm.root.time == np.datetime64(time_str)
