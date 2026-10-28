"""
The map worker (src/map_worker) with a fake pmtiles command and a mock API client, and its HTTP client with a mock
transport: no requests leave the test.
"""
import asyncio
import json
import logging
import sys
from pathlib import Path

import httpx
import pytest

from map_worker.adapters.cache import ExtractCache
from map_worker.adapters.http.abstract_client import AbstractMapAPIClient, UploadRefused
from map_worker.adapters.http.client import MapAPIClient
from map_worker.domain.job import MapJob, Extract, BadJob, check
from map_worker.fetching import PmtilesCommand, MapRegionError
from map_worker.service_layer import handlers as handlers_module
from map_worker.service_layer.handlers import MapHandlers
from map_worker.service_layer.worker import MapWorker, Unanswered

BUILD = 'https://build.protomaps.com/20261026.pmtiles'
BUILD_NEXT = 'https://build.protomaps.com/20261027.pmtiles'
OUTLINE = {'type': 'FeatureCollection', 'features': [{'type': 'Feature', 'properties': {}, 'geometry': None}]}

FAKE_PMTILES = """#!{python}
# Prints a size on a dry run, else writes a small PMTiles file after waiting the seconds in its configuration
import json, sys, time
from pathlib import Path
arguments = sys.argv[1:]
if '--dry-run' in arguments:
    print("extract.go:612: Extract transferred 1 MB (overfetch 0.05) for an archive size of 454 MB")
else:
    time.sleep(json.loads(Path({config!r}).read_text())['seconds'])
    Path(arguments[2]).write_bytes(b'PMTiles' + bytes(9))
"""


def job(kind: str, key: str, **payload) -> MapJob:
    return MapJob(kind=kind, key=key, lease='lease-1', lease_seconds=60, payload=payload)


def region(key: str = 'IRL', kind: str = 'extract', outline=OUTLINE, **changes) -> MapJob:
    return job(kind, key, **({'outline': outline, 'build': BUILD, 'minzoom': 9, 'maxzoom': 15} | changes))


class MockClient(AbstractMapAPIClient):
    def __init__(self, jobs: dict[str, list[MapJob]] | None = None):
        self.jobs = jobs or {}
        self.results, self.failures, self.uploads, self.renewals = [], [], [], []
        self.builds = []  # (key, build, version) of each file sent
        self.held = True
        self.upload_errors: list[Exception] = []

    async def lease(self, lane):
        queue = self.jobs.get(lane, [])
        return queue.pop(0) if queue else None

    async def renew(self, job):
        self.renewals.append(job.key)
        return self.held

    async def post_result(self, job, result):
        self.results.append((job.kind, job.key, result))
        return True

    async def post_failure(self, job, error):
        self.failures.append((job.kind, job.key, error))
        return True

    async def upload(self, job, extract):
        if self.upload_errors:
            raise self.upload_errors.pop(0)
        self.uploads.append((job.key, extract.path.read_bytes()))
        self.builds.append((job.key, extract.build, extract.version))
        return True


@pytest.fixture
def work(tmp_path) -> Path:
    return tmp_path / 'work'


@pytest.fixture
def pmtiles(tmp_path) -> tuple[PmtilesCommand, Path]:
    config = tmp_path / 'pmtiles.json'
    config.write_text(json.dumps({'seconds': 0}))
    command = tmp_path / 'pmtiles'
    command.write_text(FAKE_PMTILES.format(python=sys.executable, config=str(config)))
    command.chmod(0o755)
    return PmtilesCommand(str(command)), config


@pytest.fixture
def handlers(pmtiles, work) -> MapHandlers:
    handlers = MapHandlers(pmtiles[0], work, 'https://geoboundaries.example', 'https://builds.example')
    handlers.clear()
    return handlers


@pytest.fixture
def cached(pmtiles, work, tmp_path) -> MapHandlers:
    """Handlers keeping what they cut"""
    handlers = MapHandlers(pmtiles[0], work, '', '', cache=ExtractCache(tmp_path / 'cache', poll_seconds=0.05))
    handlers.clear()
    return handlers


def counting(pmtiles: PmtilesCommand) -> list:
    """The builds pmtiles cuts from"""
    cuts = []
    extract = pmtiles.extract

    async def counted(build, *args, **kwargs):
        cuts.append(build)
        return await extract(build, *args, **kwargs)
    pmtiles.extract = counted
    return cuts


def worker(client, handlers) -> MapWorker:
    worker = MapWorker(client, handlers, poll_interval=0.05)
    worker.upload_retry_seconds = 0
    return worker


""" The jobs it does """


@pytest.mark.parametrize('bad, reason', [
    (job('scrape', 'latest'), 'no such kind'),
    (job('builds', 'all'), 'not a key'),
    (job('outlines', 'USA-ADM1', code='USA', level='ADM2'), "are not USA-ADM1's"),
    (region(build='https://example.org/build.pmtiles'), "not one of Protomaps' builds"),
    (region(build=BUILD + '?x=1'), "not one of Protomaps' builds"),
    (region(minzoom=9, maxzoom=16), 'not zooms'),
    (region(minzoom=True), 'not zooms'),
    (region(outline=None), 'has no outline'),
    (region(outline={'type': 'Polygon'}), 'not a FeatureCollection'),
    (region(key='../etc'), 'not a key'),
    (region(version='4.15.2; rm -rf /'), 'not a version'),
    (region(fresh='yes'), 'fresh is not'),
])
def test_jobs_asking_for_anything_else_than_maps_are_refused(bad, reason):
    with pytest.raises(BadJob, match=reason):
        check(bad)


@pytest.mark.parametrize('good', [
    job('builds', 'latest'),
    job('outlines', 'USA-ADM1', code='USA', level='ADM1'),
    region(key='USA-ADM1-USA-ADM1-3_0_0-B1', kind='size'),
    region(key='world', outline=None, minzoom=0, maxzoom=8),
    region(version='4.15.2', fresh=True),
])
def test_jobs_for_maps_are_done(good):
    check(good)


@pytest.mark.asyncio
async def test_a_quick_job_posts_its_result(handlers, monkeypatch):
    async def builds(url):
        return [{'key': '20261026.pmtiles', 'version': '4.15.2', 'size': 1}, 'not a build']

    async def outlines(url, code, level):
        return {'boundaryLicense': 'CC BY 4.0'}, OUTLINE
    monkeypatch.setattr(handlers_module, 'list_builds', builds)
    monkeypatch.setattr(handlers_module, 'download_outlines', outlines)
    client = MockClient({'quick': [
        job('builds', 'latest'), job('outlines', 'IRL-ADM0', code='IRL', level='ADM0'), region(kind='size')
    ]})
    for _ in range(3):
        assert await worker(client, handlers).process_next('quick')
    assert client.results == [
        ('builds', 'latest', {'builds': [{'key': '20261026.pmtiles', 'version': '4.15.2'}]}),
        ('outlines', 'IRL-ADM0', {'about': {'boundaryLicense': 'CC BY 4.0'}, 'outlines': OUTLINE}),
        ('size', 'IRL', {'size': 454_000_000}),
    ]
    assert not list(handlers.work_path.iterdir()), 'the outline written for pmtiles is deleted'


@pytest.mark.asyncio
async def test_an_extract_is_uploaded_and_deleted(handlers):
    client = MockClient({'extract': [region()]})
    assert await worker(client, handlers).process_next('extract')
    assert client.uploads == [('IRL', b'PMTiles' + bytes(9))]
    assert client.builds == [('IRL', BUILD, None)]
    assert not list(handlers.work_path.iterdir())


@pytest.mark.asyncio
async def test_failures_and_refusals_are_posted(handlers, monkeypatch):
    async def unreachable(url):
        raise MapRegionError("The list of Protomaps builds could not be read: ConnectError")
    monkeypatch.setattr(handlers_module, 'list_builds', unreachable)
    client = MockClient({'quick': [job('builds', 'latest'), region(kind='size', build='https://example.org/x.pmtiles')]})
    await worker(client, handlers).process_next('quick')
    await worker(client, handlers).process_next('quick')
    assert client.failures[0] == ('builds', 'latest', "The list of Protomaps builds could not be read: ConnectError")
    assert client.failures[1][2].startswith("The map worker refused the job: not one of Protomaps' builds")
    assert not client.results


@pytest.mark.asyncio
async def test_a_refused_renewal_stops_the_extract(handlers, pmtiles):
    """The country was removed, or the lease went to another worker: pmtiles is stopped and nothing is sent"""
    pmtiles[1].write_text(json.dumps({'seconds': 30}))
    stopping = region()
    stopping.lease_seconds = 0.3
    client = MockClient({'extract': [stopping]})
    client.held = False
    await asyncio.wait_for(worker(client, handlers).process_next('extract'), 10)
    assert client.renewals == ['IRL'] and not client.uploads and not client.failures
    assert not list(handlers.work_path.iterdir())


@pytest.mark.asyncio
async def test_an_upload_broken_off_is_sent_again_unless_the_job_was_cancelled(handlers):
    client = MockClient({'extract': [region(), region(key='LUX')]})
    client.upload_errors = [httpx.ConnectError('the API restarted')]
    await worker(client, handlers).process_next('extract')
    assert [key for key, _ in client.uploads] == ['IRL']

    client.upload_errors = [httpx.ReadError('gone')]
    client.held = False
    await worker(client, handlers).process_next('extract')
    assert [key for key, _ in client.uploads] == ['IRL'] and not client.failures


@pytest.mark.asyncio
async def test_a_refused_upload_fails_the_job(handlers):
    client = MockClient({'extract': [region()]})
    client.upload_errors = [UploadRefused('not a PMTiles file')]
    await worker(client, handlers).process_next('extract')
    assert client.failures == [('extract', 'IRL', 'The API refused the file: not a PMTiles file')]


@pytest.mark.asyncio
async def test_a_long_extract_holds_up_no_quick_job(handlers, pmtiles, monkeypatch):
    async def builds(url):
        return []
    monkeypatch.setattr(handlers_module, 'list_builds', builds)
    pmtiles[1].write_text(json.dumps({'seconds': 1}))
    client = MockClient({'extract': [region()], 'quick': [job('builds', 'latest')]})
    running = worker(client, handlers)
    task = asyncio.create_task(running.run())
    try:
        for _ in range(100):
            if client.results:
                break
            await asyncio.sleep(0.02)
        assert client.results and not client.uploads, 'the quick job was done while the extract ran'
        for _ in range(200):
            if client.uploads:
                break
            await asyncio.sleep(0.02)
        assert client.uploads
    finally:
        await running.shutdown()
        await asyncio.wait_for(task, 10)


""" Its log while the API doesn't answer """


class UnansweredClient(MockClient):
    """Leaves the first polls of each lane unanswered, as while the API restarts"""
    def __init__(self, unanswered: int):
        super().__init__()
        self.unanswered = {'quick': unanswered, 'extract': unanswered}

    async def lease(self, lane):
        if self.unanswered[lane]:
            self.unanswered[lane] -= 1
            raise httpx.ConnectError('Connection refused')
        return await super().lease(lane)


@pytest.mark.asyncio
async def test_polls_unanswered_are_logged_when_they_start_and_end_not_each_time(handlers, caplog):
    client = UnansweredClient(unanswered=5)
    running = worker(client, handlers)
    with caplog.at_level(logging.INFO, logger='map_worker.service_layer.worker'):
        task = asyncio.create_task(running.run())
        try:
            for _ in range(200):
                if sum(r.getMessage().startswith('The API answers') for r in caplog.records) == 2:
                    break
                await asyncio.sleep(0.02)
        finally:
            await running.shutdown()
            await asyncio.wait_for(task, 10)
    unanswered = [r.getMessage() for r in caplog.records if 'could not be asked' in r.getMessage()]
    answered = [r.getMessage() for r in caplog.records if r.getMessage().startswith('The API answers')]
    assert sorted(m.split(' jobs')[0] for m in unanswered) == [
        'The API could not be asked for extract', 'The API could not be asked for quick'
    ]
    assert all('ConnectError: Connection refused' in m for m in unanswered)
    assert len(answered) == 2 and all(m.endswith('(5 polls unanswered)') for m in answered)
    assert not [r for r in caplog.records if r.levelno >= logging.WARNING and r.getMessage() not in unanswered]


def test_polls_unanswered_for_long_are_logged_again_each_hour(caplog):
    now = [0.0]
    unanswered = Unanswered('quick', 5, clock=lambda: now[0])
    with caplog.at_level(logging.INFO, logger='map_worker.service_layer.worker'):
        for _ in range(1000):
            unanswered.failed(httpx.ConnectError('Connection refused'))
            now[0] += 5
        unanswered.answered()
        unanswered.answered()
    assert [r.getMessage() for r in caplog.records] == [
        "The API could not be asked for quick jobs: ConnectError: Connection refused. Asking every 5 s, and saying when "
        "it answers",
        "The API has not answered for quick jobs for 1 h (721 polls): ConnectError: Connection refused",
        "The API answers for quick jobs again, after 1 h 23 min 20 s (1000 polls unanswered)",
    ]


""" Its cache """


@pytest.mark.asyncio
@pytest.mark.parametrize('first, again', [
    (region(version='4.15.2'), region(build=BUILD_NEXT, version='4.16.0')),  # a newer build of the same version
    (region(), region()),  # the same pinned build, which has no version
])
async def test_an_extract_is_kept_and_sent_again(cached, first, again):
    cuts = counting(cached.pmtiles)
    client = MockClient({'extract': [first, again]})
    for _ in range(2):
        assert await worker(client, cached).process_next('extract')
    assert cuts == [BUILD]
    assert client.builds == [('IRL', BUILD, first.payload.get('version'))] * 2, 'sent with the build it was cut from'
    assert [key for key, _ in client.uploads] == ['IRL', 'IRL']
    assert sorted(path.name for path in cached.cache.path.iterdir()) == ['.IRL.lock', 'IRL.json', 'IRL.pmtiles']
    assert not list(cached.work_path.iterdir())


@pytest.mark.asyncio
@pytest.mark.parametrize('again', [
    region(build=BUILD_NEXT, version='5.0.0'),  # another major version
    region(build=BUILD_NEXT, version='4.16.0', fresh=True),  # asked fresh, as by scripts/map_tiles.py --refresh
    region(build=BUILD_NEXT, version='4.16.0', maxzoom=14),
    region(build=BUILD_NEXT, version='4.16.0', outline={**OUTLINE, 'features': OUTLINE['features'] * 2}),
    region(build=BUILD_NEXT),  # a pinned build, which must be the same
])
async def test_an_extract_of_other_tiles_is_cut_again_and_replaces_the_one_kept(cached, again):
    cuts = counting(cached.pmtiles)
    client = MockClient({'extract': [region(version='4.15.2'), again]})
    for _ in range(2):
        assert await worker(client, cached).process_next('extract')
    assert cuts == [BUILD, BUILD_NEXT]
    assert client.builds[1] == ('IRL', BUILD_NEXT, again.payload.get('version'))
    assert json.loads((cached.cache.path / 'IRL.json').read_text())['build'] == BUILD_NEXT


@pytest.mark.asyncio
async def test_workers_sharing_a_cache_cut_a_region_once(pmtiles, tmp_path):
    """The production and demonstration sites' workers, each with a work path of its own"""
    pmtiles[1].write_text(json.dumps({'seconds': 0.5}))
    cuts = counting(pmtiles[0])
    both = []
    for site in ('production', 'demo'):
        cache = ExtractCache(tmp_path / 'cache', poll_seconds=0.05)
        handlers = MapHandlers(pmtiles[0], tmp_path / site, '', '', cache=cache)
        handlers.clear()
        both.append(handlers)
    extracts = await asyncio.wait_for(asyncio.gather(*(handlers.extract(region()) for handlers in both)), 10)
    assert cuts == [BUILD]
    assert extracts[0].path == extracts[1].path == tmp_path / 'cache' / 'IRL.pmtiles'
    assert not any(extract.temporary for extract in extracts)


""" Its HTTP client """


@pytest.mark.asyncio
async def test_the_client_leases_renews_and_uploads(tmp_path):
    requests = []

    def answer(request: httpx.Request) -> httpx.Response:
        requests.append(request)
        path = request.url.path
        if path == '/map_jobs/next/quick':
            return httpx.Response(204)
        if path == '/map_jobs/next/extract':
            return httpx.Response(200, json={
                'kind': 'extract', 'key': 'IRL', 'lease': 'abc', 'lease_seconds': 300, 'payload': {'outline': None}
            })
        if path.endswith('/renew'):
            return httpx.Response(409)
        if path.endswith('/file'):
            return httpx.Response(400, json={'detail': 'not a PMTiles file'})
        return httpx.Response(204)

    client = MapAPIClient('https://breedgraph.example/', auth_token='token')
    client.client = httpx.AsyncClient(transport=httpx.MockTransport(answer))
    assert await client.lease('quick') is None
    leased = await client.lease('extract')
    assert (leased.kind, leased.key, leased.lease, leased.lease_seconds) == ('extract', 'IRL', 'abc', 300)
    assert not await client.renew(leased)
    assert await client.post_result(leased, {'size': 1})
    file = tmp_path / 'IRL.pmtiles'
    file.write_bytes(b'tiles')
    with pytest.raises(UploadRefused, match='not a PMTiles file'):
        await client.upload(leased, Extract(file, BUILD, '4.15.2'))

    assert all(r.headers['Authorization'] == 'Bearer token' for r in requests)
    assert json.loads(requests[3].content) == {'lease': 'abc', 'result': {'size': 1}}
    put = requests[4]
    assert (put.method, put.url.path) == ('PUT', '/map_jobs/extract/IRL/file')
    assert (put.headers['X-Map-Lease'], put.headers['X-Map-Size']) == ('abc', '5')
    assert (put.headers['X-Map-Build'], put.headers['X-Map-Version']) == (BUILD, '4.15.2')
    assert file.exists(), 'the caller deletes it, if it is temporary'
