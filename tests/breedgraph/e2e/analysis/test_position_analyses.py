"""
Analyses of the positions study (tests/breedgraph/scenarios/position_scenario.py) by each viewer: the levels of each
case's position term, with the count and mean of their observations, and the records that can't be placed. What they
report is what the scenario expects, and so what the test database manifest gives breedview.
"""
import pytest

from tests.breedgraph.e2e.analysis.test_analysis_types import run_analysis, concept, analysis
from tests.breedgraph.e2e.datasets.test_datasets_read_api import query
from tests.breedgraph.scenarios.position_scenario import (
    CASES, DATASETS, VIEWERS, Level, level_key, grouping_input, term_inputs
)

TERMS = (
    "... on DescriptiveStatisticsResult { terms { levels { term { type layoutAxis } level } count mean "
    "group { locationId layoutAxes { axis layoutId value } } } }"
)


async def record_ids_by_value(client, login_token_factory, read_policy, viewer: str, dataset_id: int) -> dict[str, int]:
    found, = await query(
        client, login_token_factory, read_policy, viewer, 'datasets',
        "query ($ids: [ID!]) { datasets(ids: $ids) { status result { records { id value } } errors { name message } } }",
        {'ids': [dataset_id]}
    )
    return {record['value']: int(record['id']) for record in found['records']}


def group_of(positions, read_policy, level: Level) -> dict:
    """The AnalysisGroup fields a level sets"""
    if level.location is not None:
        return {'locationId': level_key(positions, read_policy, level), 'layoutAxes': []}
    return {'locationId': None, 'layoutAxes': [
        {'axis': level.axis, 'layoutId': str(positions.layouts[level.layout]), 'value': level.value}
    ]}


@pytest.mark.asyncio(loop_scope="session")
@pytest.mark.parametrize('viewer', VIEWERS)
@pytest.mark.parametrize('case', CASES, ids=lambda case: case.key)
async def test_case(case, viewer, read_policy, positions, login_token_factory, client):
    concept_key, _ = DATASETS[case.datasets[0]]
    submission = await run_analysis(client, login_token_factory(read_policy[viewer]), analysis(
        "DESCRIPTIVE_STATISTICS", "descriptiveStatistics", [positions.datasets[key] for key in case.datasets], {
            "terms": [concept(read_policy[concept_key], aggregation='MEAN'), *term_inputs(case)],
            "grouping": {"position": grouping_input(case, read_policy)}
        }
    ), TERMS)
    assert submission['status'] == 'COMPLETED', submission['errors']
    _, *rows = submission['result']['terms']
    found = {row['levels'][0]['level']: (row['count'], row['mean'], row['group']) for row in rows}
    expected = {
        level_key(positions, read_policy, level): (count, pytest.approx(mean), group_of(positions, read_policy, level))
        for level, (count, mean) in case.expected[viewer].items()
    }
    assert found == expected

    unassigned = next((w for w in submission['warnings'] if w['code'] == 'UNASSIGNED_POSITION'), None)
    if not case.unassigned:
        assert unassigned is None, unassigned
        return
    assert unassigned is not None, submission['warnings']
    ids = await record_ids_by_value(
        client, login_token_factory, read_policy, viewer, positions.datasets[case.datasets[0]]
    )
    assert sorted(int(i) for i in unassigned['recordIds']) == sorted(ids[value] for value in case.unassigned)
    assert unassigned['path'] == ['descriptiveStatistics', 'grouping', 'position']
