import pytest
from src.breedgraph.domain.model.datasets import DataSetStored, DataRecordInput


from src.breedgraph.custom_exceptions import NoResultFoundError

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
    async for d in datasets_repo.get_all(term_id=height_variable.id):
        if d == stored_dataset:
            break
    else:
        raise NoResultFoundError("Couldn't find created dataset by get all with term id")

@pytest.mark.asyncio(scope="session")
async def test_update_contributors(
        datasets_repo,
        stored_dataset,
        stored_person
):
    stored_dataset.contributors.remove(stored_person.id)
    await datasets_repo.update_seen()
    retrieved = await datasets_repo.get(dataset_id = stored_dataset.id)
    assert stored_dataset == retrieved
    stored_dataset.contributors.append(stored_person.id)
    await datasets_repo.update_seen()
    retrieved = await datasets_repo.get(dataset_id=stored_dataset.id)
    assert stored_dataset == retrieved

@pytest.mark.asyncio(scope="session")
async def test_add_record_to_existing_unit(
        datasets_repo,
        stored_dataset,
        stored_person,
        tree_block
):
    records = stored_dataset.unit_records[tree_block.root.id]
    new_record = DataRecordInput(value=50)
    records.append(new_record)
    await datasets_repo.update_seen()
    retrieved = await datasets_repo.get(dataset_id = stored_dataset.id)
    assert len(retrieved.unit_records[tree_block.root.id]) == len(records)

@pytest.mark.asyncio(scope="session")
async def test_add_new_unit_record(
        datasets_repo,
        stored_dataset,
        stored_person,
        second_tree_block
):
    records = stored_dataset.unit_records[second_tree_block.root.id]
    new_record = DataRecordInput(value=50)
    records.append(new_record)
    await datasets_repo.update_seen()
    retrieved = await datasets_repo.get(dataset_id = stored_dataset.id)
    assert len(retrieved.unit_records[second_tree_block.root.id]) == len(records)
