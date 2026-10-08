"""
End-to-end tests for each analysis type:
submit through GraphQL, lease the job as the worker, run it, post the outcome and query the result.
"""
import asyncio

import pytest
import pytest_asyncio

from breedgraph.config import GQL_API_PATH
from breedgraph.domain.model.datasets import DataRecordInput
from breedgraph.domain.model.submissions import SubmissionStatus
from numpy import datetime64

from analysis_worker.domain.model.job import AnalysisJob, AnalysisJobFailed
from analysis_worker.service_layer.runner import run_job

from tests.breedgraph.e2e.analysis.post_methods import post_to_submit_analysis, worker_headers
from tests.breedgraph.e2e.utils import get_verified_payload, assert_payload_success, with_auth
from tests.breedgraph.scenarios.block_builder import BlockBuilder
from tests.breedgraph.scenarios.dataset_builder import DatasetBuilder
from tests.breedgraph.scenarios.germplasm_builder import GermplasmBuilder
from tests.breedgraph.scenarios.ontology_builder import OntologyBuilder

UNITS_PER_GERMPLASM = 4


@pytest_asyncio.fixture(scope="module", loop_scope="session")
async def analysis_context(dataset_build_context, uow_factory) -> dict:
    """
    Two germplasm with four units each. Height is recorded for each unit in 2020 and 2021,
    light once per unit. The last unit has an outlying height.
    """
    user_id = dataset_build_context['user_id']
    study_id = dataset_build_context['study_id']
    height_id = dataset_build_context['concept_id']
    light_id = (await OntologyBuilder(uow_factory).factor_light_intensity(user_id))['ontology_factor_light']

    germplasm_ids = [await GermplasmBuilder(uow_factory).germplasm(user_id) for _ in range(2)]
    units = []
    for g, germplasm_id in enumerate(germplasm_ids):
        for u in range(UNITS_PER_GERMPLASM):
            units.append((await BlockBuilder(uow_factory).unit(user_id, germplasm_id=germplasm_id), g, u))

    height_records, light_records = [], []
    for i, (unit_id, g, u) in enumerate(units):
        for year in (0, 1):
            value = 1000 + 300 * g + 50 * year + 7 * u + (5000 if i == len(units) - 1 and year == 0 else 0)
            height_records.append(DataRecordInput(unit=unit_id, value=str(value), start=datetime64(f"202{year}-06-01")))
        light_records.append(DataRecordInput(unit=unit_id, value=str(100 + 10 * i + 5 * g), start=datetime64("2020-06-01")))

    builder = DatasetBuilder(uow_factory)
    height_dataset = (await builder.dataset(user_id, height_id, study_id, records=height_records))['dataset_id']
    light_dataset = (await builder.dataset(user_id, light_id, study_id, records=light_records))['dataset_id']
    return {
        'user_id': user_id,
        'height_id': height_id,
        'light_id': light_id,
        'germplasm_ids': germplasm_ids,
        'unit_ids': [u[0] for u in units],
        'height_dataset': height_dataset,
        'light_dataset': light_dataset,
    }


async def post_to_get_result(client, token: str, analysis_id: str, fragment: str):
    json = {
        "query": (
            " query ( $id: ID! ) { analysisSubmission( id: $id ) { status, errors { name, message } "
            "  result { status, errors { code, message, path, recordIds }, warnings { code, message, path } "
            f"   result {{ {fragment} }} "
            " } } } "
        ),
        "variables": {"id": analysis_id}
    }
    headers = with_auth(csrf_token=client.headers["X-CSRF-Token"], auth_token=token)
    return await client.post(GQL_API_PATH, json=json, headers=headers)


async def run_analysis(client, token: str, analysis: dict, fragment: str) -> dict:
    """Submit an analysis, process it as the worker would and return the submission."""
    payload = get_verified_payload(await post_to_submit_analysis(client, token, analysis), "analysisSubmit")
    assert_payload_success(payload)
    analysis_id = payload['result']

    async def get():
        response = await post_to_get_result(client, token, analysis_id, fragment)
        payload = get_verified_payload(response, "analysisSubmission")
        assert_payload_success(payload)
        return payload['result']

    for _ in range(30):
        await asyncio.sleep(0.1)
        submission = await get()
        if submission['status'] in ('QUEUED', 'FAILED'):
            break
    assert submission['status'] == SubmissionStatus.QUEUED.name, submission['errors']

    response = await client.get("/analysis_jobs/next", headers=worker_headers())
    assert response.status_code == 200
    leased = response.json()
    assert leased['analysis_id'] == analysis_id
    job = AnalysisJob(**leased)
    try:
        outcome = run_job(job)
        body = {
            'lease': job.lease, 'analysis_id': analysis_id, 'analysis_type': job.analysis_type,
            'result': outcome.result, 'warnings': [w.model_dump() for w in outcome.warnings]
        }
        response = await client.post(f"/analysis_jobs/{analysis_id}/result", json=body, headers=worker_headers())
    except AnalysisJobFailed as e:
        body = {
            'lease': job.lease,
            'errors': [m.model_dump() for m in e.errors], 'warnings': [m.model_dump() for m in e.warnings]
        }
        response = await client.post(f"/analysis_jobs/{analysis_id}/failure", json=body, headers=worker_headers())
    assert response.status_code == 204, response.text
    return await get()


def concept(concept_id, **options):
    return {"reference": {"type": "CONCEPT", "conceptId": concept_id}, **options}

def analysis(analysis_type: str, field: str, dataset_ids: list, spec: dict) -> dict:
    return {"analysisType": analysis_type, "datasetIds": dataset_ids, field: spec}

GERMPLASM_TERM = {"reference": {"type": "GERMPLASM"}}

def germplasm_grouping(context):
    return {"germplasm": {"germplasmIds": context['germplasm_ids']}}

YEARS = {
    "time": {
        "assignment": "START",
        "binning": {"boundaries": ["2021-01-01"], "labels": ["2020", "2021"], "boundary": "RIGHT"}
    }
}


@pytest.mark.asyncio(loop_scope="session")
async def test_descriptive_statistics(analysis_context, login_token_factory, client):
    token = login_token_factory(analysis_context['user_id'])
    submission = await run_analysis(client, token, analysis(
        "DESCRIPTIVE_STATISTICS", "descriptiveStatistics", [analysis_context['height_dataset']], {
            "terms": [concept(analysis_context['height_id'], aggregation="MEAN"), GERMPLASM_TERM],
            "grouping": germplasm_grouping(analysis_context),
            "estimatedMeans": [{"terms": [{"type": "GERMPLASM"}]}]
        }
    ), (
        "... on DescriptiveStatisticsResult { "
        " terms { term { conceptId } levels { term { type } level } group { germplasmId } count mean } "
        " estimatedMeans { response { conceptId } means { levels { level } mean } "
        "   contrasts { label levelsA { level } levelsB { level } pValue significant } } }"
    ))
    assert submission['status'] == 'COMPLETED', submission['errors']
    result = submission['result']
    overall, *by_germplasm = result['terms']
    assert overall['levels'] == [] and overall['count'] == 2 * UNITS_PER_GERMPLASM
    assert [t['group']['germplasmId'] for t in by_germplasm] == [str(g) for g in analysis_context['germplasm_ids']]
    assert all(t['count'] == UNITS_PER_GERMPLASM for t in by_germplasm)
    means, = result['estimatedMeans']
    assert means['response']['conceptId'] == str(analysis_context['height_id'])
    assert len(means['means']) == 2
    contrast, = means['contrasts']
    assert [contrast['levelsA'][0]['level'], contrast['levelsB'][0]['level']] == [str(g) for g in analysis_context['germplasm_ids']]


@pytest.mark.asyncio(loop_scope="session")
async def test_correlation(analysis_context, login_token_factory, client):
    token = login_token_factory(analysis_context['user_id'])
    submission = await run_analysis(client, token, analysis(
        "CORRELATION", "correlation", [analysis_context['height_dataset'], analysis_context['light_dataset']], {
            "terms": [
                concept(analysis_context['height_id'], aggregation="MEDIAN"),
                concept(analysis_context['light_id'])
            ],
            "method": "SPEARMAN"
        }
    ), "... on CorrelationResult { terms { conceptId } matrix { term { conceptId } values } }")
    assert submission['status'] == 'COMPLETED', submission['errors']
    matrix = submission['result']['matrix']
    assert matrix[0]['values'][0] == pytest.approx(1.0)
    assert matrix[0]['values'][1] == pytest.approx(matrix[1]['values'][0])
    assert matrix[0]['values'][1] > 0.9


@pytest.mark.asyncio(loop_scope="session")
async def test_outlier_detection(analysis_context, login_token_factory, client):
    token = login_token_factory(analysis_context['user_id'])
    submission = await run_analysis(client, token, analysis(
        "OUTLIER_DETECTION", "outlierDetection", [analysis_context['height_dataset']], {
            "terms": [concept(analysis_context['height_id']), {"reference": {"type": "TIME"}}],
            "grouping": YEARS,
            "method": "IQR"
        }
    ), (
        "... on OutlierDetectionResult { outliers { observation { unitId time } "
        " exclusion { unitIds start end } term { conceptId } value score } }"
    ))
    assert submission['status'] == 'COMPLETED', submission['errors']
    outlier = submission['result']['outliers'][0]
    outlying_unit = str(analysis_context['unit_ids'][-1])
    assert outlier['observation'] == {'unitId': outlying_unit, 'time': '2020'}
    # a rule excluding the observation in a subsequent analysis
    assert outlier['exclusion']['unitIds'] == [outlying_unit]
    assert outlier['exclusion']['start'] is None and outlier['exclusion']['end'].startswith('2021-01-01')


@pytest.mark.asyncio(loop_scope="session")
async def test_mds(analysis_context, login_token_factory, client):
    token = login_token_factory(analysis_context['user_id'])
    submission = await run_analysis(client, token, analysis(
        "MDS", "mds", [analysis_context['height_dataset'], analysis_context['light_dataset']], {
            "terms": [concept(analysis_context['height_id'], aggregation="MEAN"), concept(analysis_context['light_id'])],
            "distance": "EUCLIDEAN",
            "clustering": {"method": "KMEANS", "clusters": 2}
        }
    ), "... on MDSResult { observations { group { unitId } recordIds coordinates clusterId } }")
    assert submission['status'] == 'COMPLETED', submission['errors']
    observations = submission['result']['observations']
    assert len(observations) == 2 * UNITS_PER_GERMPLASM
    assert all(len(o['coordinates']) == 2 and len(o['recordIds']) == 3 for o in observations)
    assert len({o['clusterId'] for o in observations}) == 2


ANOVA_FRAGMENT = (
    "... on AnovaResult { "
    " terms { term { type conceptId } degreesOfFreedom denominatorDegreesOfFreedom sumOfSquares fStatistic pValue } "
    " randomEffects { group { type } slope { type } variance standardDeviation } "
    " estimatedMeans { means { levels { level } mean } contrasts { label significant } } "
    " residual { degreesOfFreedom } }"
)

@pytest.mark.asyncio(loop_scope="session")
async def test_anova_linear_model(analysis_context, login_token_factory, client):
    pytest.importorskip("rpy2")
    token = login_token_factory(analysis_context['user_id'])
    submission = await run_analysis(client, token, analysis(
        "ANOVA", "anova", [analysis_context['height_dataset']], {
            "terms": [concept(analysis_context['height_id']), GERMPLASM_TERM, {"reference": {"type": "TIME"}}],
            "response": {"type": "CONCEPT", "conceptId": analysis_context['height_id']},
            "grouping": germplasm_grouping(analysis_context) | YEARS,
            "estimatedMeans": [{"terms": [{"type": "GERMPLASM"}], "adjustment": "HOLM"}]
        }
    ), ANOVA_FRAGMENT)
    assert submission['status'] == 'COMPLETED', submission['errors']
    result = submission['result']
    assert [t['term']['type'] for t in result['terms']] == ['GERMPLASM', 'TIME']
    assert result['randomEffects'] == []
    # 16 observations, 3 fixed parameters
    assert result['residual']['degreesOfFreedom'] == 13
    assert len(result['estimatedMeans'][0]['contrasts']) == 1


@pytest.mark.asyncio(loop_scope="session")
async def test_anova_mixed_model(analysis_context, login_token_factory, client):
    pytest.importorskip("rpy2")
    token = login_token_factory(analysis_context['user_id'])
    submission = await run_analysis(client, token, analysis(
        "ANOVA", "anova", [analysis_context['height_dataset']], {
            "terms": [
                concept(analysis_context['height_id']),
                GERMPLASM_TERM,
                {"reference": {"type": "TIME"}},
                {"reference": {"type": "UNIT"}, "effect": "RANDOM"}
            ],
            "response": {"type": "CONCEPT", "conceptId": analysis_context['height_id']},
            "grouping": germplasm_grouping(analysis_context) | YEARS,
            "ddf": "KENWARD_ROGER"
        }
    ), ANOVA_FRAGMENT)
    assert submission['status'] == 'COMPLETED', submission['errors']
    result = submission['result']
    assert all(t['denominatorDegreesOfFreedom'] is not None for t in result['terms'])
    random, = result['randomEffects']
    assert random['group'] == {'type': 'UNIT'} and random['slope'] is None
    assert result['residual'] is None


@pytest.mark.asyncio(loop_scope="session")
async def test_duplicate_observations_fail_before_queueing(analysis_context, login_token_factory, client):
    token = login_token_factory(analysis_context['user_id'])
    payload = get_verified_payload(await post_to_submit_analysis(client, token, analysis(
        "DESCRIPTIVE_STATISTICS", "descriptiveStatistics", [analysis_context['height_dataset']],
        {"terms": [concept(analysis_context['height_id'])]}
    )), "analysisSubmit")
    analysis_id = payload['result']
    for _ in range(30):
        await asyncio.sleep(0.1)
        response = await post_to_get_result(client, token, analysis_id, "__typename")
        submission = get_verified_payload(response, "analysisSubmission")['result']
        if submission['status'] == 'FAILED':
            break
    error, = submission['errors']
    assert error['code'] == 'DUPLICATE_OBSERVATION'
    assert error['path'] == ['descriptiveStatistics', 'terms', '0', 'aggregation']
    assert len(error['recordIds']) == 4 * UNITS_PER_GERMPLASM
