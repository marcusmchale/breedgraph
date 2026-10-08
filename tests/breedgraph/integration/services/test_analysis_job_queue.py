import pytest

from breedgraph.domain.model.submissions import SubmissionStatus, SubmissionKeys


@pytest.mark.asyncio(loop_scope="session")
async def test_analysis_job_lease_and_complete(state_store):
    analysis_id = await state_store.store_analysis(agent_id=1, analysis={'analysis_type': 'ANOVA'})
    assert await state_store.get_status(1, analysis_id) == SubmissionStatus.PENDING

    await state_store.enqueue_analysis_job(analysis_id, {'rows': [[1.0]]}, warnings=[{'code': 'EMPTY_DATASET'}])
    assert await state_store.get_status(1, analysis_id) == SubmissionStatus.QUEUED

    leased_id, lease, payload = await state_store.lease_analysis_job(lease_seconds=60)
    assert leased_id == analysis_id and payload == {'rows': [[1.0]]}
    assert await state_store.get_status(1, analysis_id) == SubmissionStatus.PROCESSING
    assert await state_store.lease_analysis_job(lease_seconds=60) is None

    assert not await state_store.complete_analysis_job(analysis_id, 'not the lease', {}, [])
    assert await state_store.complete_analysis_job(
        analysis_id, lease, {'analysis_type': 'ANOVA'}, [{'code': 'MODEL_NOT_CONVERGED'}]
    )
    assert await state_store.get_status(1, analysis_id) == SubmissionStatus.COMPLETED
    assert await state_store.get_analysis_result(1, analysis_id) == {'analysis_type': 'ANOVA'}
    assert [w['code'] for w in await state_store.get_analysis_warnings(1, analysis_id)] == [
        'EMPTY_DATASET', 'MODEL_NOT_CONVERGED'
    ]
    assert await state_store.get_analysis_errors(1, analysis_id) == []
    assert await state_store._get_json(analysis_id, SubmissionKeys.JOB) is None
    # the lease was released
    assert not await state_store.fail_analysis_job(analysis_id, lease, [{'code': 'INTERNAL_ERROR'}], [])


@pytest.mark.asyncio(loop_scope="session")
async def test_expired_lease_is_requeued(state_store):
    analysis_id = await state_store.store_analysis(agent_id=1, analysis={'analysis_type': 'ANOVA'})
    await state_store.enqueue_analysis_job(analysis_id, {}, warnings=[])
    _, first_lease, _ = await state_store.lease_analysis_job(lease_seconds=0)

    _, second_lease, _ = await state_store.lease_analysis_job(lease_seconds=60)
    assert second_lease != first_lease
    # a late report from the first lease is rejected
    assert not await state_store.fail_analysis_job(analysis_id, first_lease, [{'code': 'INTERNAL_ERROR'}], [])
    assert await state_store.fail_analysis_job(analysis_id, second_lease, [{'code': 'MODEL_FAILED'}], [])
    assert await state_store.get_status(1, analysis_id) == SubmissionStatus.FAILED
    assert [e['code'] for e in await state_store.get_analysis_errors(1, analysis_id)] == ['MODEL_FAILED']


@pytest.mark.asyncio(loop_scope="session")
async def test_analysis_messages_are_replaced_and_reset(state_store):
    analysis_id = await state_store.store_analysis(agent_id=1, analysis={'analysis_type': 'ANOVA'})
    await state_store.set_analysis_messages(analysis_id, errors=[{'code': 'A'}], warnings=[{'code': 'B'}])
    await state_store.set_analysis_messages(analysis_id, errors=[{'code': 'C'}], warnings=[])
    assert await state_store.get_analysis_errors(1, analysis_id) == [{'code': 'C'}]
    await state_store.reset_analysis_messages(analysis_id)
    assert await state_store.get_analysis_errors(1, analysis_id) == []
    with pytest.raises(ValueError):
        await state_store.get_analysis_errors(2, analysis_id)


@pytest.mark.asyncio(loop_scope="session")
async def test_delete_analysis(state_store):
    analysis_id = await state_store.store_analysis(agent_id=1, analysis={'analysis_type': 'ANOVA'})
    await state_store.enqueue_analysis_job(analysis_id, {}, warnings=[])
    _, lease, _ = await state_store.lease_analysis_job(lease_seconds=0)

    with pytest.raises(ValueError):
        await state_store.delete_analysis(2, analysis_id)
    await state_store.delete_analysis(1, analysis_id)

    assert analysis_id not in await state_store.get_user_analyses(1)
    with pytest.raises(ValueError):
        await state_store.get_analysis_config(1, analysis_id)
    # the lease is not re-queued and a late report from the worker is rejected
    assert await state_store.lease_analysis_job(lease_seconds=60) is None
    assert not await state_store.complete_analysis_job(analysis_id, lease, {}, [])
