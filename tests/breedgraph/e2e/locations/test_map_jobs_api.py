"""The map worker's routes (entrypoints/fastapi/map_jobs.py), with jobs queued in the state store as the API queues them"""
import json
from pathlib import Path

import pytest
import pytest_asyncio

from breedgraph import config

PMTILES = b'PMTiles' + bytes(25)
OUTLINES = {'type': 'FeatureCollection', 'features': [
    {'type': 'Feature', 'properties': {'shapeID': 'irl'}, 'geometry': {'type': 'Point', 'coordinates': [-8, 53]}}
]}


def worker_headers(**headers) -> dict:
    return {"Authorization": f"Bearer {config.MAP_WORKER_AUTH_TOKEN}", **headers}


@pytest_asyncio.fixture(loop_scope="session")
async def jobs(state_store):
    """Each test starts with no map state"""
    async def clear():
        async for key in state_store.connection.scan_iter(match='map:*'):
            await state_store.connection.delete(key)
    await clear()
    yield state_store
    await clear()


async def lease(client, lane: str) -> dict:
    response = await client.get(f"/map_jobs/next/{lane}", headers=worker_headers())
    assert response.status_code == 200, response.text
    return response.json()


@pytest.mark.asyncio(loop_scope="session")
async def test_the_routes_need_the_map_workers_token_and_a_lane(client, jobs):
    assert (await client.get("/map_jobs/next/quick")).status_code == 401
    assert (await client.get("/map_jobs/next/quick", headers={"Authorization": "Bearer wrong"})).status_code == 401
    assert (await client.get("/map_jobs/next/slow", headers=worker_headers())).status_code == 404
    assert (await client.get("/map_jobs/next/quick", headers=worker_headers())).status_code == 204


@pytest.mark.asyncio(loop_scope="session")
async def test_a_size_is_leased_renewed_and_returned(client, jobs):
    await jobs.enqueue_map_job('size', 'IRL', {'outline': OUTLINES, 'build': 'b', 'minzoom': 9, 'maxzoom': 15})
    job = await lease(client, 'quick')
    assert {key: job[key] for key in ('kind', 'key', 'lease_seconds')} == {
        'kind': 'size', 'key': 'IRL', 'lease_seconds': config.MAP_JOB_LEASE_SECONDS
    }
    assert job['payload']['outline'] == OUTLINES

    renew = "/map_jobs/size/IRL/renew"
    assert (await client.post(renew, json={'lease': job['lease']}, headers=worker_headers())).status_code == 204
    assert (await client.post(renew, json={'lease': 'stale'}, headers=worker_headers())).status_code == 409
    result = "/map_jobs/size/IRL/result"
    assert (await client.post(result, json={'lease': 'stale', 'result': {'size': 1}}, headers=worker_headers())).status_code == 409
    assert (await client.post(result, json={'lease': job['lease'], 'result': {'size': 454}}, headers=worker_headers())).status_code == 204
    assert (await jobs.get_map_job('size', 'IRL'))['result'] == {'size': 454}


@pytest.mark.asyncio(loop_scope="session")
async def test_outlines_are_kept_before_their_job_is_done(client, jobs):
    await jobs.enqueue_map_job('outlines', 'IRL-ADM0', {'code': 'IRL', 'level': 'ADM0'})
    job = await lease(client, 'quick')
    response = await client.post("/map_jobs/outlines/IRL-ADM0/result", headers=worker_headers(), json={
        'lease': job['lease'], 'result': {'about': {'boundaryLicense': 'CC BY 4.0'}, 'outlines': OUTLINES}
    })
    assert response.status_code == 204
    boundaries = Path(config.MAP_BOUNDARIES_PATH)
    assert json.loads((boundaries / 'IRL-ADM0.geojson').read_text()) == OUTLINES
    assert json.loads((boundaries / 'IRL-ADM0.json').read_text()) == {'boundaryLicense': 'CC BY 4.0'}
    assert (await jobs.get_map_job('outlines', 'IRL-ADM0'))['state'] == 'done'


@pytest.mark.asyncio(loop_scope="session")
async def test_a_bad_result_fails_its_job(client, jobs):
    await jobs.enqueue_map_job('size', 'LUX', {})
    job = await lease(client, 'quick')
    response = await client.post("/map_jobs/size/LUX/result", headers=worker_headers(), json={
        'lease': job['lease'], 'result': {'size': 'large'}
    })
    assert response.status_code == 204
    failed = await jobs.get_map_job('size', 'LUX')
    assert (failed['state'], failed['error']) == ('failed', "The map worker sent a bad result: the size is not a number of bytes")


@pytest.mark.asyncio(loop_scope="session")
async def test_an_extract_is_kept_under_a_name_the_api_makes(client, jobs):
    await jobs.enqueue_map_job('extract', 'IRL', {})
    job = await lease(client, 'extract')
    response = await client.put("/map_jobs/extract/IRL/file", content=PMTILES, headers=worker_headers(**{
        'X-Map-Lease': job['lease'], 'X-Map-Size': str(len(PMTILES))
    }))
    assert response.status_code == 204, response.text
    result = (await jobs.get_map_job('extract', 'IRL'))['result']
    assert result == {'file': f".IRL.{job['lease']}.upload", 'size': len(PMTILES)}
    assert (Path(config.MAP_TILES_PATH) / 'regions' / result['file']).read_bytes() == PMTILES


@pytest.mark.asyncio(loop_scope="session")
@pytest.mark.parametrize('content, size, status', [
    (PMTILES, len(PMTILES) + 1, 400),  # shorter than announced
    (PMTILES, len(PMTILES) - 1, 400),  # longer
    (b'not tiles at all', 16, 400),
])
async def test_a_bad_extract_is_refused_and_nothing_kept(client, jobs, content, size, status):
    await jobs.enqueue_map_job('extract', 'LUX', {})
    job = await lease(client, 'extract')
    response = await client.put("/map_jobs/extract/LUX/file", content=content, headers=worker_headers(**{
        'X-Map-Lease': job['lease'], 'X-Map-Size': str(size)
    }))
    assert response.status_code == status
    assert not list((Path(config.MAP_TILES_PATH) / 'regions').glob('.LUX.*'))
    assert (await jobs.get_map_job('extract', 'LUX'))['leased'], 'the worker may send it again'


@pytest.mark.asyncio(loop_scope="session")
async def test_an_extract_of_a_cancelled_job_is_refused(client, jobs):
    await jobs.enqueue_map_job('extract', 'LUX', {})
    job = await lease(client, 'extract')
    await jobs.remove_map_country('LUX')
    response = await client.put("/map_jobs/extract/LUX/file", content=PMTILES, headers=worker_headers(**{
        'X-Map-Lease': job['lease'], 'X-Map-Size': str(len(PMTILES))
    }))
    assert response.status_code == 409
    assert not list((Path(config.MAP_TILES_PATH) / 'regions').glob('.LUX.*'))


@pytest.mark.asyncio(loop_scope="session")
async def test_a_failure_is_kept_for_whoever_waits(client, jobs):
    await jobs.enqueue_map_job('builds', 'latest', {})
    job = await lease(client, 'quick')
    failure = {'lease': job['lease'], 'error': 'The list of Protomaps builds could not be read: ConnectError'}
    assert (await client.post("/map_jobs/builds/latest/failure", json=failure, headers=worker_headers())).status_code == 204
    assert (await jobs.get_map_job('builds', 'latest'))['error'] == failure['error']
    assert (await client.post("/map_jobs/builds/latest/failure", json=failure, headers=worker_headers())).status_code == 409
