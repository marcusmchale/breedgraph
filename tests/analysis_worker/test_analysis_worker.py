from concurrent.futures import Executor, Future
from concurrent.futures.process import BrokenProcessPool

import pytest

from analysis_worker.adapters.http.abstract_client import AbstractAnalysisAPIClient
from analysis_worker.domain.model.job import AnalysisJob, AnalysisOutcome, Message, ErrorCode
from analysis_worker.service_layer import runner
from analysis_worker.service_layer.worker import AnalysisWorker


class MockAnalysisAPIClient(AbstractAnalysisAPIClient):
    def __init__(self, jobs: list[AnalysisJob]):
        self.jobs = list(jobs)
        self.results = []
        self.failures = []

    async def lease_job(self):
        return self.jobs.pop(0) if self.jobs else None

    async def post_result(self, job, result, warnings):
        self.results.append((job.analysis_id, result, warnings))
        return True

    async def post_failure(self, job, errors, warnings):
        self.failures.append((job.analysis_id, errors, warnings))
        return True

    async def close(self):
        pass


def job(analysis_type='ANOVA') -> AnalysisJob:
    return AnalysisJob(analysis_id='a1', lease='l1', lease_seconds=60, payload={
        'analysis_type': analysis_type,
        'config': {},
        'columns': [
            {'name': 'concept:1', 'kind': 'CONTINUOUS', 'levels': None, 'term': {}},
            {'name': 'germplasm', 'kind': 'CATEGORICAL', 'levels': ['2', '3'], 'term': {}},
        ],
        'rows': [[1.0, '2'], [None, '3']],
        'observations': [{}, {}]
    })


def test_job_frame():
    frame = job().frame()
    assert frame['concept:1'].isna().tolist() == [False, True]
    assert list(frame['germplasm'].cat.categories) == ['2', '3']


@pytest.mark.asyncio
async def test_unimplemented_analysis_is_reported_as_failure():
    client = MockAnalysisAPIClient([job()])
    worker = AnalysisWorker(client)
    assert await worker.process_next()
    assert not await worker.process_next()
    (analysis_id, errors, _), = client.failures
    assert analysis_id == 'a1'
    assert errors[0].code == ErrorCode.INTERNAL_ERROR
    assert client.results == []


@pytest.mark.asyncio
async def test_result_is_posted(monkeypatch):
    monkeypatch.setitem(runner.ANALYSES, 'ANOVA', lambda j: AnalysisOutcome(result={'terms': []}))
    client = MockAnalysisAPIClient([job()])
    await AnalysisWorker(client).process_next()
    assert client.results == [('a1', {'terms': []}, [])]


@pytest.mark.asyncio
async def test_unexpected_error_is_reported_without_details(monkeypatch):
    def broken(_):
        raise RuntimeError("secret detail")
    monkeypatch.setitem(runner.ANALYSES, 'ANOVA', broken)
    client = MockAnalysisAPIClient([job()])
    await AnalysisWorker(client).process_next()
    (_, errors, _), = client.failures
    assert errors[0].code == ErrorCode.INTERNAL_ERROR and "secret" not in errors[0].message


@pytest.mark.asyncio
async def test_running_out_of_memory_is_reported_as_such(monkeypatch):
    def hungry(_):
        raise MemoryError()
    monkeypatch.setitem(runner.ANALYSES, 'ANOVA', hungry)
    client = MockAnalysisAPIClient([job()])
    await AnalysisWorker(client).process_next()
    (_, errors, _), = client.failures
    assert errors[0].code == ErrorCode.INTERNAL_ERROR and 'memory' in errors[0].message


class EndingExecutor(Executor):
    """A process pool whose first process ends abruptly, as one killed for its memory does, which breaks the pool"""
    made = 0

    def __init__(self):
        EndingExecutor.made += 1
        self.broken = EndingExecutor.made == 1

    def submit(self, fn, /, *args, **kwargs):
        future = Future()
        if self.broken:
            future.set_exception(BrokenProcessPool('A process in the process pool was terminated abruptly'))
        else:
            future.set_result(fn(*args, **kwargs))
        return future


@pytest.mark.asyncio
async def test_an_analysis_whose_process_ends_is_reported_and_the_next_runs_in_a_new_pool(monkeypatch):
    monkeypatch.setitem(runner.ANALYSES, 'ANOVA', lambda j: AnalysisOutcome(result={'terms': []}))
    monkeypatch.setattr(EndingExecutor, 'made', 0)
    client = MockAnalysisAPIClient([job(), job()])
    worker = AnalysisWorker(client, executor_factory=EndingExecutor)
    await worker.process_next()
    await worker.process_next()
    (_, errors, _), = client.failures
    assert errors[0].code == ErrorCode.INTERNAL_ERROR and 'memory' in errors[0].message
    assert client.results == [('a1', {'terms': []}, [])]
    assert EndingExecutor.made == 2
