import pytest, pytest_asyncio

from breedgraph.domain.model.datasets import DatasetInput, DataRecordInput


from typing import Dict

import logging
logger = logging.getLogger(__name__)


@pytest_asyncio.fixture(scope="module", loop_scope="session")
async def dataset_with_records(
        uow_factory,
        dataset_build_context
) -> Dict[str, int]:
    user_id = dataset_build_context['user_id']
    concept_id = dataset_build_context['concept_id']
    study_id = dataset_build_context['study_id']
    unit_id = dataset_build_context['unit_id']
    dataset_input = DatasetInput(
        concept=concept_id,
        study=study_id
    )
    async with uow_factory.get_uow(user_id=user_id) as uow:
        dataset = await uow.repositories.datasets.create(dataset_input)
        for i in range(10):
            new_record = DataRecordInput(unit=unit_id, value=str(i))
            dataset.records.append(new_record)
        await uow.commit()
    return {
        'user_id': user_id,
        'dataset_id':dataset.id,
        'study_id': study_id
    }

@pytest.mark.asyncio(loop_scope="session")
async def test_get_dataset_summaries(
        views_factory,
        dataset_with_records
):
    user_id = dataset_with_records['user_id']
    async with views_factory.get_views(user_id=user_id) as views:
        summaries = await views.datasets.get_dataset_summaries(study_id=dataset_with_records['study_id'])
        assert summaries, f"Expected dataset summaries for study {dataset_with_records['study_id']}, but got none"

