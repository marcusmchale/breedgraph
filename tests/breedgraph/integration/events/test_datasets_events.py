import pytest

from breedgraph.domain.events.datasets import DatasetSubmitted
from breedgraph.domain.model.submissions import SubmissionStatus
from breedgraph.service_layer.handlers.events.datasets import handle_dataset_submitted

@pytest.mark.asyncio(loop_scope="session")
async def test_create_dataset_command(
        bus,
        event_queue,
        uow_factory,
        views_factory,
        state_store,
        lorem_text_generator,
        dataset_build_context
):
    user_id: int = dataset_build_context['user_id']
    study_id: int = dataset_build_context['study_id']

    records = [{
        'unit_id': dataset_build_context['unit_id'],
        'value': f'{i * 10}',
        'start': '2010'
    } for i in range(3)]
    records += [{
        'unit_id': dataset_build_context['unit_id'],
        'value': f'{i * 20}',
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
        write_team=dataset_build_context['team_id'],
        submission_id=submission_id
    )
    await bus.handle(event)
    await event_queue.join()

    status = await state_store.get_status(agent_id=user_id, key=submission_id)
    assert status == SubmissionStatus.COMPLETED
    errors = await state_store.get_errors(agent_id=user_id, key=submission_id)
    item_errors = await state_store.get_submission_item_errors(agent_id=user_id, submission_id=submission_id)
    assert not any([errors, item_errors])

    dataset_id = await state_store.get_submission_dataset_id(agent_id=user_id, submission_id=submission_id)
    async with views_factory.get_views(user_id=user_id) as views:
        dataset_summaries = await views.datasets.get_dataset_summaries(study_id=study_id)
        assert dataset_summaries
        for summary in dataset_summaries:
            if summary.id == dataset_id:
                assert summary.concept_id == dataset_build_context['concept_id']
                assert summary.record_count == len(records)
                assert summary.unit_count == 1
                break
        else:
            raise RuntimeError(f'Dataset summary for {dataset_id} not found')






@pytest.mark.asyncio(loop_scope="session")
async def test_citing_an_unreadable_reference_fails_the_submission(
        bus,
        event_queue,
        uow_factory,
        state_store,
        dataset_build_context
):
    from breedgraph.domain.commands.references import CreateExternalReference
    from tests.breedgraph.scenarios.account_builder import AccountBuilder

    other = await AccountBuilder(uow_factory=uow_factory).account_with_affiliations()
    hidden_id = await bus.handle(CreateExternalReference(
        agent_id=other['user_id'], write_team=other['team_id'], url='https://example.org/hidden'
    ))
    user_id: int = dataset_build_context['user_id']
    record = {'unit_id': dataset_build_context['unit_id'], 'value': '1', 'start': '2012'}
    for dataset_input in (
        {'reference_ids': [hidden_id], 'records': [record]},
        {'records': [{**record, 'reference_ids': [hidden_id]}]}
    ):
        submission_id = await state_store.store_submission(agent_id=user_id, submission={
            'study_id': dataset_build_context['study_id'],
            'concept_id': dataset_build_context['concept_id'],
            **dataset_input
        })
        await bus.handle(DatasetSubmitted(agent_id=user_id, write_team=dataset_build_context['team_id'], submission_id=submission_id))
        await event_queue.join()
        assert await state_store.get_status(agent_id=user_id, key=submission_id) == SubmissionStatus.FAILED
        assert 'NoResultFoundError' in str(await state_store.get_errors(agent_id=user_id, key=submission_id))


@pytest.mark.asyncio(loop_scope="session")
async def test_a_reference_cited_by_a_record_keeps_the_release_of_its_dataset(
        bus,
        event_queue,
        uow_factory,
        state_store,
        dataset_build_context
):
    from breedgraph.custom_exceptions import IllegalOperationError
    from breedgraph.domain.commands.controls import SetRelease
    from breedgraph.domain.commands.references import CreateExternalReference
    from breedgraph.domain.model.controls import ControlledModelLabel, ReadRelease

    user_id: int = dataset_build_context['user_id']
    reference_id = await bus.handle(CreateExternalReference(
        agent_id=user_id, write_team=dataset_build_context['team_id'], release=ReadRelease.PUBLIC, url='https://example.org/method'
    ))
    submission_id = await state_store.store_submission(agent_id=user_id, submission={
        'study_id': dataset_build_context['study_id'],
        'concept_id': dataset_build_context['concept_id'],
        'records': [{'unit_id': dataset_build_context['unit_id'], 'value': '1', 'start': '2013', 'reference_ids': [reference_id]}]
    })
    await bus.handle(DatasetSubmitted(
        agent_id=user_id, write_team=dataset_build_context['team_id'], release=ReadRelease.REGISTERED, submission_id=submission_id
    ))
    await event_queue.join()
    assert await state_store.get_status(agent_id=user_id, key=submission_id) == SubmissionStatus.COMPLETED

    def set_release(release):
        return SetRelease(agent_id=user_id, entity_ids=[reference_id], entity_label=ControlledModelLabel.REFERENCE, release=release)
    with pytest.raises(IllegalOperationError):
        await bus.handle(set_release(ReadRelease.PRIVATE))
    await bus.handle(set_release(ReadRelease.REGISTERED))
