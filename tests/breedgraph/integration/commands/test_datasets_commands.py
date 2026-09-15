import pytest

from breedgraph.domain.commands.datasets import CreateDataset, UpdateDataset, AddRecords, RemoveRecords


@pytest.mark.asyncio(loop_scope="session")
async def test_create_dataset_command(
        bus,
        uow_factory,
        state_store,
        lorem_text_generator,
        dataset_build_context
):
    user_id = dataset_build_context['user_id']
    records = [{
        'unit_id': dataset_build_context['unit_id'],
        'value': f'{i * 10}'
    } for i in range(3)]
    dataset_input = {
        'study_id': dataset_build_context['study_id'],
        'concept_id': dataset_build_context['concept_id'],
        'records': records
    }
    submission_id = await state_store.store_submission(agent_id=user_id, submission=dataset_input)

    cmd = CreateDataset(
        agent_id=user_id,
        submission_id=submission_id
    )
    await bus.handle_command(cmd)
