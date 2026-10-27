"""The map worker's jobs in the state store (adapters/redis/state_store.py, adapters/pmtiles/jobs.py)"""
import pytest
import pytest_asyncio


@pytest_asyncio.fixture(loop_scope="session")
async def jobs(state_store):
    """Each test starts with no map state"""
    async for key in state_store.connection.scan_iter(match='map:*'):
        await state_store.connection.delete(key)
    yield state_store


@pytest.mark.asyncio(loop_scope="session")
async def test_a_job_is_leased_renewed_and_finished(jobs):
    await jobs.enqueue_map_job('size', 'IRL', {'outline': None})
    assert (await jobs.get_map_job('size', 'IRL'))['state'] == 'queued'

    kind, key, lease, payload = await jobs.lease_map_job('quick', 60)
    assert (kind, key, payload) == ('size', 'IRL', {'outline': None})
    assert (await jobs.get_map_job('size', 'IRL'))['leased']
    assert await jobs.lease_map_job('quick', 60) is None

    assert not await jobs.renew_map_job('size', 'IRL', 'not the lease', 60)
    assert await jobs.renew_map_job('size', 'IRL', lease, 60)
    assert not await jobs.finish_map_job('size', 'IRL', 'not the lease', result={'size': 1})
    assert await jobs.finish_map_job('size', 'IRL', lease, result={'size': 454})
    job = await jobs.get_map_job('size', 'IRL')
    assert (job['state'], job['leased'], job['result']) == ('done', False, {'size': 454})
    # the lease ended with it
    assert not await jobs.renew_map_job('size', 'IRL', lease, 60)


@pytest.mark.asyncio(loop_scope="session")
async def test_a_job_queued_or_leased_is_joined_not_queued_again(jobs):
    await jobs.enqueue_map_job('outlines', 'USA-ADM1', {'code': 'USA', 'level': 'ADM1'})
    await jobs.enqueue_map_job('outlines', 'USA-ADM1', {'code': 'USA', 'level': 'ADM1'})
    _, _, lease, _ = await jobs.lease_map_job('quick', 60)
    await jobs.enqueue_map_job('outlines', 'USA-ADM1', {'code': 'USA', 'level': 'ADM1'})
    assert await jobs.lease_map_job('quick', 60) is None
    assert await jobs.renew_map_job('outlines', 'USA-ADM1', lease, 60)


@pytest.mark.asyncio(loop_scope="session")
async def test_a_finished_job_is_queued_again_unless_a_done_one_is_reused(jobs):
    for kind, lane in (('size', 'quick'), ('extract', 'extract')):
        await jobs.enqueue_map_job(kind, 'IRL', {})
        _, _, lease, _ = await jobs.lease_map_job(lane, 60)
        await jobs.finish_map_job(kind, 'IRL', lease, result={'kept': True})
    # a size is asked again; a done extract, whose file waits to be taken, is reused
    await jobs.enqueue_map_job('size', 'IRL', {})
    await jobs.enqueue_map_job('extract', 'IRL', {}, reuse_done=True)
    assert (await jobs.get_map_job('size', 'IRL'))['state'] == 'queued'
    assert (await jobs.get_map_job('extract', 'IRL'))['result'] == {'kept': True}
    # one that failed is tried again
    _, _, lease, _ = await jobs.lease_map_job('quick', 60)
    await jobs.finish_map_job('size', 'IRL', lease, error='geoBoundaries could not be reached')
    assert (await jobs.get_map_job('size', 'IRL'))['error'] == 'geoBoundaries could not be reached'
    await jobs.enqueue_map_job('size', 'IRL', {})
    assert (await jobs.get_map_job('size', 'IRL'))['state'] == 'queued'


@pytest.mark.asyncio(loop_scope="session")
async def test_extracts_wait_in_a_lane_of_their_own(jobs):
    await jobs.enqueue_map_job('extract', 'USA-ADM1-a', {})
    await jobs.enqueue_map_job('size', 'USA-ADM1-b', {})
    assert (await jobs.lease_map_job('quick', 60))[:2] == ('size', 'USA-ADM1-b')
    assert (await jobs.lease_map_job('extract', 60))[:2] == ('extract', 'USA-ADM1-a')


@pytest.mark.asyncio(loop_scope="session")
async def test_an_expired_lease_is_queued_again_and_the_old_one_refused(jobs):
    await jobs.enqueue_map_job('extract', 'IRL', {})
    _, _, first, _ = await jobs.lease_map_job('extract', 0)
    _, _, second, _ = await jobs.lease_map_job('extract', 60)
    assert second != first
    assert not await jobs.renew_map_job('extract', 'IRL', first, 60)
    assert not await jobs.finish_map_job('extract', 'IRL', first, result={})
    assert await jobs.finish_map_job('extract', 'IRL', second, result={})


@pytest.mark.asyncio(loop_scope="session")
async def test_removing_a_country_deletes_its_jobs_and_no_others(jobs):
    await jobs.enqueue_map_job('outlines', 'USA-ADM1', {})
    await jobs.enqueue_map_job('size', 'USA-ADM1-a', {})
    await jobs.enqueue_map_job('extract', 'USA', {})
    await jobs.enqueue_map_job('extract', 'IRL', {})
    await jobs.enqueue_map_job('builds', 'latest', {})
    _, _, lease, _ = await jobs.lease_map_job('extract', 60)  # USA's, leased

    await jobs.remove_map_country('USA')
    for kind, key in (('outlines', 'USA-ADM1'), ('size', 'USA-ADM1-a'), ('extract', 'USA')):
        assert await jobs.get_map_job(kind, key) is None
    # the worker's lease is refused at its next renewal
    assert not await jobs.renew_map_job('extract', 'USA', lease, 60)
    assert (await jobs.lease_map_job('extract', 60))[:2] == ('extract', 'IRL')
    assert (await jobs.lease_map_job('quick', 60))[:2] == ('builds', 'latest')
    assert await jobs.lease_map_job('quick', 60) is None


@pytest.mark.asyncio(loop_scope="session")
async def test_a_deleted_job_is_not_leased(jobs):
    await jobs.enqueue_map_job('size', 'IRL', {})
    await jobs.enqueue_map_job('size', 'LUX', {})
    await jobs.delete_map_job('size', 'IRL')
    assert (await jobs.lease_map_job('quick', 60))[:2] == ('size', 'LUX')
    assert await jobs.lease_map_job('quick', 60) is None
    assert [key async for key in jobs.connection.scan_iter(match='map:job:size:IRL')] == []
