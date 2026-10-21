"""
Analyses of the arrivals study's samples (tests/breedgraph/scenarios/arrival_scenario.py), run as the writer: what
comes down their unit graph. A sample's germplasm is its trees' (expected_germplasm), so one pooled from trees of two
varieties is unassigned; and the light recorded on its trees describes its height (EXPECTED_LIGHT), so one pooled from
trees whose lights differ takes neither, with FACTOR_LINEAGES_DIFFER naming those records.
"""
from collections import Counter

import pytest

from tests.breedgraph.e2e.analysis.test_analysis_types import run_analysis, concept, analysis, GERMPLASM_TERM
from tests.breedgraph.e2e.datasets.test_datasets_read_api import query
from tests.breedgraph.scenarios.arrival_scenario import EXPECTED_LIGHT, HEIGHT, expected_germplasm

TERMS = "... on DescriptiveStatisticsResult { terms { term { type conceptId } group { germplasmId } count mean } }"


def warning(submission, code: str) -> dict | None:
    return next((w for w in submission['warnings'] if w['code'] == code), None)


async def record_ids_by_unit(client, login_token_factory, read_policy, dataset_id: int) -> dict[int, int]:
    found, = await query(
        client, login_token_factory, read_policy, 'writer', 'datasets',
        "query ($ids: [ID!]) { datasets(ids: $ids) { status result { records { id unit { id } } } errors { name message } } }",
        {'ids': [dataset_id]}
    )
    return {int(record['unit']['id']): int(record['id']) for record in found['records']}


@pytest.mark.asyncio(loop_scope="session")
async def test_the_trees_light_describes_their_samples_height(read_policy, arrivals, login_token_factory, client):
    height, light = read_policy['ontology_variable_height'], read_policy['ontology_factor_light']
    submission = await run_analysis(client, login_token_factory(read_policy['writer']), analysis(
        "DESCRIPTIVE_STATISTICS", "descriptiveStatistics", [arrivals.datasets['height'], arrivals.datasets['light']],
        {"terms": [concept(height), concept(light)]}
    ), TERMS)
    assert submission['status'] == 'COMPLETED', submission['errors']
    terms = {int(term['term']['conceptId']): term for term in submission['result']['terms']}
    assert terms[height]['count'] == len(HEIGHT)
    lights = [float(value) for value in EXPECTED_LIGHT.values() if value is not None]
    assert (terms[light]['count'], terms[light]['mean']) == (len(lights), pytest.approx(sum(lights) / len(lights)))
    # the pooled sample's trees, Tree A and Tree B, were given different lights
    light_records = await record_ids_by_unit(client, login_token_factory, read_policy, arrivals.datasets['light'])
    differing = warning(submission, 'FACTOR_LINEAGES_DIFFER')
    assert differing is not None, submission['warnings']
    assert sorted(int(i) for i in differing['recordIds']) == sorted(
        light_records[arrivals.units[name]] for name in ('Arrival Tree A', 'Arrival Tree B')
    )


@pytest.mark.asyncio(loop_scope="session")
async def test_samples_are_grouped_by_the_germplasm_they_inherit(read_policy, arrivals, login_token_factory, client):
    germplasm = expected_germplasm(arrivals, 'writer')
    selected = sorted({value['germplasm'] for name in HEIGHT if (value := germplasm[name]) is not None})
    submission = await run_analysis(client, login_token_factory(read_policy['writer']), analysis(
        "DESCRIPTIVE_STATISTICS", "descriptiveStatistics", [arrivals.datasets['height']], {
            "terms": [concept(read_policy['ontology_variable_height']), GERMPLASM_TERM],
            "grouping": {"germplasm": {"germplasmIds": [read_policy[key] for key in selected]}}
        }
    ), TERMS)
    assert submission['status'] == 'COMPLETED', submission['errors']
    _, *by_germplasm = submission['result']['terms']
    expected = Counter(germplasm[name]['germplasm'] for name in HEIGHT if germplasm[name] is not None)
    assert {int(t['group']['germplasmId']): t['count'] for t in by_germplasm} == {
        read_policy[key]: count for key, count in expected.items()
    }
    # a sample pooled from trees of two varieties has none, and its record is unassigned
    height_records = await record_ids_by_unit(client, login_token_factory, read_policy, arrivals.datasets['height'])
    unassigned = warning(submission, 'UNASSIGNED_GERMPLASM')
    assert unassigned is not None, submission['warnings']
    assert [int(i) for i in unassigned['recordIds']] == [
        height_records[arrivals.units[name]] for name in HEIGHT if germplasm[name] is None
    ]
