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
