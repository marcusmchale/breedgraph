import pytest

from breedgraph.domain.events.datasets import DatasetSubmitted
from breedgraph.domain.model.submissions import SubmissionStatus
from breedgraph.service_layer.handlers.events.datasets import handle_dataset_submitted

@pytest.mark.asyncio(loop_scope="session")
async def test_create_dataset_command(
        uow_factory,
        views_factory,
        event_queue,
        state_store,
        lorem_text_generator,
        dataset_build_context
):
    user_id: int = dataset_build_context['user_id']
    study_id: int = dataset_build_context['study_id']
    grouping: str = dataset_build_context['groupings'][0]
    records = [{
        'unit_id': dataset_build_context['unit_id'],
        'value': f'{i * 10}',
        'groups': [{'name':grouping, 'code':f'R1.{ i+1 }'}],
        'start': '2010'
    } for i in range(3)]
    records += [{
        'unit_id': dataset_build_context['unit_id'],
        'value': f'{i * 20}',
        'groups': [{'name':grouping, 'code':f'R1.{ i+ 1 }'}],
        'start': '2011'
    } for i in range(3)]

    dataset_input = {
        'study_id': study_id,
        'concept_id': dataset_build_context['concept_id'],
        'records': records
    }
    submission_id = await state_store.store_submission(agent_id=user_id, submission=dataset_input)

    event = DatasetSubmitted(
        agent_id=user_id,
        submission_id=submission_id
    )

    await handle_dataset_submitted(event, state_store, uow_factory)
    status = await state_store.get_status(agent_id=user_id, key=submission_id)
    assert status == SubmissionStatus.COMPLETED
    errors = await state_store.get_errors(agent_id=user_id, key=submission_id)
    item_errors = await state_store.get_submission_item_errors(agent_id=user_id, submission_id=submission_id)
    assert not any([errors, item_errors])

    dataset_id = state_store.get_submission_dataset_id(agent_id=user_id, submission_id=submission_id)
    async with views_factory.get_views(user_id=user_id) as views:
        dataset_summaries = await views.datasets.get_dataset_summaries(study_id=study_id)
        assert dataset_summaries
        for summary in dataset_summaries:
            if summary.id == dataset_id:
                assert summary.concept_id == dataset_build_context['concept_id']
                assert summary.record_count == len(records)
                assert summary.unit_count == 1
        import pdb; pdb.set_trace()



