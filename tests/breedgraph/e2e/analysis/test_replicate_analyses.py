"""
Analyses of the replicates study (tests/breedgraph/scenarios/replicate_scenario.py), run as the writer: what they
report is what the scenario expects, and so what the test database manifest gives breedview.
"""
import pytest

from tests.breedgraph.e2e.analysis.test_analysis_types import run_analysis, concept, analysis
from tests.breedgraph.scenarios.replicate_scenario import (
    EXPECTED_CASES, EXPECTED_WINDOWED_READINGS, EXPECTED_PLOT_MEANS, CONCEPTS, TREES,
    REPLICATE, BIOREP, BLOCK, BATCH, DATASET_BLOCK, level_keys, Case
)

DESCRIPTIVE = "... on DescriptiveStatisticsResult { terms { levels { level } count mean } }"
MDS = "... on MDSResult { observations { group { recordGroups { level unitId code shared } } recordIds } }"


def concept_id(read_policy, concept: str) -> int:
    return read_policy[CONCEPTS[concept][0]]


def concept_of(dataset: str) -> str:
    return {
        'width': 'width', 'biorep_width': 'width', 'factor': 'light'
    }.get(dataset, 'height')


def case_id(case: Case) -> str:
    replicates = f"{case.replicate_aggregation[0]}-{case.replicate_aggregation[1] or 'exact'}" if case.replicate_aggregation else "none"
    return f"{case.dataset}-{case.aggregation}-{replicates}"


@pytest.mark.asyncio(loop_scope="session")
@pytest.mark.parametrize('case', EXPECTED_CASES, ids=case_id)
async def test_case(case, read_policy, replicates, login_token_factory, client):
    options = {'aggregation': case.aggregation}
    if case.replicate_aggregation:
        aggregation, window = case.replicate_aggregation
        options['replicateAggregation'] = {'aggregation': aggregation, 'window': window}
    submission = await run_analysis(client, login_token_factory(read_policy['writer']), analysis(
        "DESCRIPTIVE_STATISTICS", "descriptiveStatistics", [replicates.datasets[case.dataset]],
        {"terms": [concept(concept_id(read_policy, concept_of(case.dataset)), **options)]}
    ), DESCRIPTIVE)
    if case.error:
        code, path_end, record_count = case.error
        assert submission['status'] == 'FAILED'
        error, = submission['errors']
        assert (error['code'], error['path'][-1], len(error['recordIds'])) == (code, path_end, record_count)
        return
    assert submission['status'] == 'COMPLETED', submission['errors']
    warnings = {warning['code'] for warning in submission['warnings']}
    assert warnings & {'REPLICATES_POOLED'} == set(case.warnings)


@pytest.mark.asyncio(loop_scope="session")
@pytest.mark.parametrize('window', [w for w in EXPECTED_WINDOWED_READINGS if w])
async def test_windowed_readings(window, read_policy, replicates, login_token_factory, client):
    """With a term mean, each tree counts once; the replicate mean's window decides how many readings it averages"""
    submission = await run_analysis(client, login_token_factory(read_policy['writer']), analysis(
        "DESCRIPTIVE_STATISTICS", "descriptiveStatistics", [replicates.datasets['windowed']], {"terms": [concept(
            concept_id(read_policy, 'height'), aggregation='MEAN',
            replicateAggregation={'aggregation': 'MEAN', 'window': window}
        )]}
    ), DESCRIPTIVE)
    assert submission['status'] == 'COMPLETED', submission['errors']
    overall, = submission['result']['terms']
    assert overall['count'] == len(TREES)
    # the windowed values are 1200 + 100 * tree index + 10 * code at codes 1, 2 and 3 (see _windowed)
    readings = EXPECTED_WINDOWED_READINGS[window]
    reading_means = {2: (15 + 30) / 2, 1: 20}[readings]
    assert overall['mean'] == pytest.approx(1200 + 100 * (len(TREES) - 1) / 2 + reading_means)


@pytest.mark.asyncio(loop_scope="session")
@pytest.mark.parametrize('replicate_mean', [False, True], ids=['pooled', 'mean_of_tree_means'])
async def test_plot_means(replicate_mean, read_policy, replicates, login_token_factory, client):
    options = {'aggregation': 'MEAN'}
    if replicate_mean:
        options['replicateAggregation'] = {'aggregation': 'MEAN'}
    plots = {replicates.units[plot]: plot for plot in EXPECTED_PLOT_MEANS}
    submission = await run_analysis(client, login_token_factory(read_policy['writer']), analysis(
        "DESCRIPTIVE_STATISTICS", "descriptiveStatistics", [replicates.datasets['same_time']], {
            "terms": [concept(concept_id(read_policy, 'height'), **options), {"reference": {"type": "UNIT"}}],
            "grouping": {"unit": {"unitIds": list(plots)}}
        }
    ), DESCRIPTIVE)
    assert submission['status'] == 'COMPLETED', submission['errors']
    _, *by_plot = submission['result']['terms']
    found = {plots[int(row['levels'][0]['level'])]: row['mean'] for row in by_plot}
    assert found == {plot: means[1 if replicate_mean else 0] for plot, means in EXPECTED_PLOT_MEANS.items()}


@pytest.mark.asyncio(loop_scope="session")
@pytest.mark.parametrize('datasets, grouping', [
    (('same_time', 'width'), REPLICATE),
    (('biorep', 'biorep_width'), BIOREP),
])
async def test_within_unit_levels(datasets, grouping, read_policy, replicates, login_token_factory, client):
    """A record group dimension of a WITHIN_UNIT grouping keeps each replicate, keyed by its tree, and pairs the
    replicates of height and width, whose codes are the same reading"""
    submission = await run_analysis(client, login_token_factory(read_policy['writer']), analysis(
        "MDS", "mds", [replicates.datasets[key] for key in datasets], {
            "terms": [concept(concept_id(read_policy, 'height')), concept(concept_id(read_policy, 'width'))],
            "distance": "EUCLIDEAN",
            "grouping": {"recordGroups": [{"name": "replicate", "groupingIds": [replicates.groupings[grouping]]}]}
        }
    ), MDS)
    assert submission['status'] == 'COMPLETED', submission['errors']
    observations = submission['result']['observations']
    levels = sorted(o['group']['recordGroups'][0]['level'] for o in observations)
    assert levels == level_keys(replicates, datasets[0], grouping) == level_keys(replicates, datasets[1], grouping)
    assert all(len(o['recordIds']) == 2 for o in observations)


async def term_levels(client, token, replicates, read_policy, dataset: str, grouping: str, levels=None) -> dict[str, int]:
    dimension = {"name": "group", "groupingIds": [replicates.groupings[grouping]]}
    if levels:
        dimension['levels'] = levels
    submission = await run_analysis(client, token, analysis(
        "DESCRIPTIVE_STATISTICS", "descriptiveStatistics", [replicates.datasets[dataset]], {
            "terms": [concept(concept_id(read_policy, 'height')), {"reference": {"type": "RECORD_GROUP", "recordGroupDimension": "group"}}],
            "grouping": {"recordGroups": [dimension]}
        }
    ), DESCRIPTIVE)
    assert submission['status'] == 'COMPLETED', submission['errors']
    _, *rows = submission['result']['terms']
    return {row['levels'][0]['level']: row['count'] for row in rows}


@pytest.mark.asyncio(loop_scope="session")
@pytest.mark.parametrize('dataset, grouping', [
    ('blocks', BLOCK), ('blocks', BATCH), ('regrouped', DATASET_BLOCK)
])
async def test_term_levels(dataset, grouping, read_policy, replicates, login_token_factory, client):
    """WITHIN_GRAPH codes are a level per field, SHARED codes one across fields"""
    found = await term_levels(client, login_token_factory(read_policy['writer']), replicates, read_policy, dataset, grouping)
    assert sorted(found) == level_keys(replicates, dataset, grouping)
    assert sum(found.values()) == len(TREES)


@pytest.mark.asyncio(loop_scope="session")
async def test_shared_block_level(read_policy, replicates, login_token_factory, client):
    """A shared level of "Block 1" merges it across the fields"""
    found = await term_levels(
        client, login_token_factory(read_policy['writer']), replicates, read_policy, 'blocks', BLOCK,
        levels=[{"label": "Block 1", "members": [{"groupingId": replicates.groupings[BLOCK], "code": "Block 1"}]}]
    )
    nested = level_keys(replicates, 'blocks', BLOCK)
    assert sorted(found) == sorted(["Block 1", *(key for key in nested if not key.endswith("|Block 1"))])
    assert len(found) == len(nested) - 1
    assert found["Block 1"] == len(TREES) // 2
