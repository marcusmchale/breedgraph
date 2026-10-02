import pytest

from breedgraph.domain.commands.datasets import CreateDataset, UpdateDataset, AddRecords, RemoveRecords
from breedgraph.domain.events.datasets import DatasetSubmitted
from breedgraph.domain.model import SubmissionStatus


@pytest.mark.asyncio(loop_scope="session")
async def test_create_dataset_command(
        bus,
        event_queue,
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

    assert event_queue.qsize() == 1
    event = event_queue.get_nowait()
    assert isinstance(event, DatasetSubmitted)
    event_queue.task_done()

    submission_data = await state_store.get_submission_data(agent_id=user_id, submission_id=submission_id)
    assert submission_data == dataset_input
    submission_status = await state_store.get_status(agent_id=user_id, key=submission_id)
    assert submission_status == SubmissionStatus.PENDING
