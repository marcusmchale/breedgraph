import pytest

from breedgraph.domain.model.datasets import DatasetInput, DataRecordInput
from breedgraph.custom_exceptions import NoResultFoundError

async def create_dataset(uow_factory, user_id, dataset_input):
    async with uow_factory.get_uow(user_id=user_id) as uow:
        await uow.repositories.datasets.create(dataset_input)
        await uow.commit()

@pytest.mark.asyncio(loop_scope="session")
async def test_create_and_get(
        uow_factory,
        dataset_build_context
):
    user_id = dataset_build_context['user_id']
    concept_id = dataset_build_context['concept_id']
    study_id = dataset_build_context['study_id']
    dataset_input = DatasetInput(
        concept=concept_id,
        study=study_id
    )
    await create_dataset(uow_factory, user_id, dataset_input)
    async with uow_factory.get_uow(user_id=user_id) as uow:
        async for d in uow.repositories.datasets.get_all():
            assert d.concept == dataset_input.concept
            assert d.study == dataset_input.study
            break
        else:
            raise NoResultFoundError("Couldn't find created dataset by get all")

        async for d in uow.repositories.datasets.get_all(concept_ids=[concept_id]):
            assert d.study == dataset_input.study
            break
        else:
            raise NoResultFoundError("Couldn't find created dataset by get all with ontology id")


@pytest.mark.asyncio(loop_scope="session")
async def test_update_contributors(
        uow_factory,
        dataset_build_context
):
    user_id = dataset_build_context['user_id']
    concept_id = dataset_build_context['concept_id']
    study_id = dataset_build_context['study_id']
    person_id = dataset_build_context['person_id']
    dataset_input = DatasetInput(
        concept=concept_id,
        study=study_id
    )
    await create_dataset(uow_factory, user_id, dataset_input)

    async with uow_factory.get_uow(user_id=user_id) as uow:
        dataset = await uow.repositories.datasets.get()
        dataset.contributors.append(person_id)
        await uow.commit()

    async with uow_factory.get_uow(user_id=user_id) as uow:
        dataset = await uow.repositories.datasets.get(dataset_id=dataset.id)
        assert person_id in dataset.contributors

        dataset.contributors.remove(person_id)
        await uow.commit()

    async with uow_factory.get_uow(user_id=user_id) as uow:
        dataset = await uow.repositories.datasets.get(dataset_id=dataset.id)
        assert person_id not in dataset.contributors


@pytest.mark.asyncio(loop_scope="session")
async def test_add_record(
        uow_factory,
        dataset_build_context
):
    user_id = dataset_build_context['user_id']
    concept_id = dataset_build_context['concept_id']
    study_id = dataset_build_context['study_id']
    dataset_input = DatasetInput(
        concept=concept_id,
        study=study_id
    )
    await create_dataset(uow_factory, user_id, dataset_input)

    unit_id = dataset_build_context['unit_id']
    async with uow_factory.get_uow(user_id=user_id) as uow:
        dataset = await uow.repositories.datasets.get()
        if dataset is None:
            raise ValueError("Dataset not found to add record")
        new_record = DataRecordInput(unit=unit_id, value='50')
        dataset.records.append(new_record)
        await uow.repositories.datasets.update_seen()

        retrieved = await uow.repositories.datasets.get(dataset_id = dataset.id)
        if not retrieved:
            raise ValueError("Dataset not found to compare length of records")
        assert len(retrieved.records) == 1
