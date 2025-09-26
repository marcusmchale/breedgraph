import pytest
from src.breedgraph.domain.model.datasets import DataSetStored, DataRecordInput

from src.breedgraph.custom_exceptions import NoResultFoundError


@pytest.mark.usefixtures("session_database")
@pytest.mark.asyncio(scope="session")
async def test_get(
        datasets_repo,
        stored_dataset,
        height_variable
):
    retrieved: DataSetStored = await datasets_repo.get(dataset_id=1)
    assert retrieved == stored_dataset
    async for d in datasets_repo.get_all():
        if d == stored_dataset:
            break
    else:
        raise NoResultFoundError("Couldn't find created dataset by get all")
    async for d in datasets_repo.get_all(concept_id=height_variable.id):
        if d == stored_dataset:
            break
    else:
        raise NoResultFoundError("Couldn't find created dataset by get all with ontology id")

@pytest.mark.asyncio(scope="session")
async def test_update_contributors(
        datasets_repo,
        stored_dataset,
        unstored_person
):
    stored_dataset.contributors.remove(unstored_person.id)
    await datasets_repo.update_seen()
    retrieved = await datasets_repo.get(dataset_id = stored_dataset.id)
    assert stored_dataset == retrieved
    stored_dataset.contributors.append(unstored_person.id)
    await datasets_repo.update_seen()
    retrieved = await datasets_repo.get(dataset_id=stored_dataset.id)
    assert stored_dataset == retrieved

@pytest.mark.asyncio(scope="session")
async def test_add_record_to_existing_unit(
        datasets_repo,
        stored_dataset,
        unstored_person,
        tree_block
):
    new_record = DataRecordInput(unit=tree_block.get_root_id(), value='50')
    stored_dataset.records.append(new_record)
    await datasets_repo.update_seen()
    retrieved = await datasets_repo.get(dataset_id = stored_dataset.id)

    assert len(retrieved.records) == len(stored_dataset.records)

@pytest.mark.asyncio(scope="session")
async def test_add_new_unit_record(
        datasets_repo,
        stored_dataset,
        unstored_person,
        second_tree_block
):
    new_record = DataRecordInput(unit=second_tree_block.root.id, value='50')
    stored_dataset.records.append(new_record)
    await datasets_repo.update_seen()
    retrieved = await datasets_repo.get(dataset_id = stored_dataset.id)
    assert len(retrieved.records) == len(stored_dataset.records)
