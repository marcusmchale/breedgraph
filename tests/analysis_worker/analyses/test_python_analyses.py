import json

import numpy as np
import pytest

from analysis_worker.domain.model.job import AnalysisJobFailed, ErrorCode, WarningCode
from analysis_worker.service_layer.runner import run_job

from .payloads import concept, domain, column, job

X, Y, Z = concept(1), concept(2), concept(3)


def test_correlation():
    rows = [[1.0, 2.0, None], [2.0, 4.0, 1.0], [3.0, 6.0, None], [4.0, 8.0, None]]
    outcome = run_job(job('CORRELATION', {'method': 'PEARSON'}, [column(X), column(Y), column(Z)], rows))
    matrix = {tuple(r['term'].values()): r['values'] for r in outcome.result['matrix']}
    assert matrix[tuple(X.values())][:2] == pytest.approx([1.0, 1.0])
    # too few pairwise complete observations
    assert matrix[tuple(X.values())][2] is None
    json.dumps(outcome.result, allow_nan=False)

def test_spearman_with_ordinal():
    levels = ['low', 'mid', 'high']
    rows = [[1.0, 'low'], [5.0, 'mid'], [9.0, 'high'], [10.0, 'high']]
    outcome = run_job(job('CORRELATION', {'method': 'SPEARMAN'}, [column(X), column(Y, 'ORDINAL', levels)], rows))
    assert outcome.result['matrix'][0]['values'][1] > 0.9


def test_descriptive_overall_and_by_level():
    germplasm = domain('GERMPLASM')
    rows = [[1.0, '5'], [3.0, '5'], [10.0, '6'], [None, '6']]
    outcome = run_job(job(
        'DESCRIPTIVE_STATISTICS', {'interactions': [], 'estimated_means': []},
        [column(X), column(germplasm, 'CATEGORICAL', ['5', '6'])], rows
    ))
    overall, five, six = outcome.result['terms']
    assert overall['levels'] == [] and overall['count'] == 3 and overall['missing_count'] == 1
    assert five['levels'] == [{'term': germplasm, 'level': '5'}]
    assert five['mean'] == 2.0 and five['standard_deviation'] == pytest.approx(np.sqrt(2))
    # all levels are of domain terms
    assert five['group'] is not None and overall['group'] is None
    assert six['count'] == 1 and six['standard_deviation'] is None
    assert outcome.warnings == []

def test_descriptive_single_level_warning():
    rows = [[1.0, 'a'], [2.0, 'a']]
    outcome = run_job(job(
        'DESCRIPTIVE_STATISTICS', {'interactions': [], 'estimated_means': []},
        [column(X), column(Y, 'CATEGORICAL', ['a', 'b'])], rows
    ))
    assert [w.code for w in outcome.warnings] == [WarningCode.SINGLE_LEVEL_TERM]


def test_an_ordinal_term_is_summarised_by_its_categories():
    """A disease score: counts in the scale's order, quartiles as scores (none averaged), by germplasm too"""
    germplasm = domain('GERMPLASM')
    scores = ['1', '3', '5', '7', '9']
    rows = [['3', '5'], ['3', '5'], ['5', '5'], ['9', '5'], ['7', '6'], ['7', '6'], [None, '6']]
    outcome = run_job(job(
        'DESCRIPTIVE_STATISTICS', {'interactions': [], 'estimated_means': []},
        [column(X, 'ORDINAL', scores), column(germplasm, 'CATEGORICAL', ['5', '6'])], rows
    ))
    overall, five, six = outcome.result['terms']
    assert [overall['count'], overall['missing_count']] == [6, 1]
    assert overall['ordinal']['categories'] == [
        {'level': '1', 'count': 0, 'share': 0.0}, {'level': '3', 'count': 2, 'share': 2 / 6},
        {'level': '5', 'count': 1, 'share': 1 / 6}, {'level': '7', 'count': 2, 'share': 2 / 6},
        {'level': '9', 'count': 1, 'share': 1 / 6}
    ]
    # 3 3 5 7 7 9: the median is the first score half reach, 5, not a mean of 5 and 7
    assert {k: overall['ordinal'][k] for k in ('minimum', 'lower_quartile', 'median', 'upper_quartile', 'maximum')} == {
        'minimum': '3', 'lower_quartile': '3', 'median': '5', 'upper_quartile': '7', 'maximum': '9'
    }
    assert 'mean' not in overall and 'standard_deviation' not in overall
    assert five['levels'] == [{'term': germplasm, 'level': '5'}] and five['group'] is not None
    assert [five['ordinal']['median'], six['ordinal']['median'], six['missing_count']] == ['3', '7', 1]
    json.dumps(outcome.result, allow_nan=False)


def test_continuous_and_ordinal_terms_are_described_in_the_order_given():
    """The height by score, as before, and the score, not grouped by itself"""
    rows = [['3', 10.0], ['3', 12.0], ['5', 20.0]]
    outcome = run_job(job(
        'DESCRIPTIVE_STATISTICS', {'interactions': [], 'estimated_means': []},
        [column(Y, 'ORDINAL', ['3', '5']), column(X)], rows
    ))
    terms = outcome.result['terms']
    assert [(t['term'], [level['level'] for level in t['levels']]) for t in terms] == [(Y, []), (X, []), (X, ['3']), (X, ['5'])]
    assert terms[0]['ordinal']['median'] == '3' and terms[2]['mean'] == 11.0
    # a score with nothing observed has no quartiles
    empty = run_job(job(
        'DESCRIPTIVE_STATISTICS', {'interactions': [], 'estimated_means': []}, [column(Y, 'ORDINAL', ['3', '5'])], [[None]]
    )).result['terms'][0]
    assert empty['count'] == 0 and empty['ordinal']['median'] is None
    assert [c['share'] for c in empty['ordinal']['categories']] == [None, None]


def normal_rows(n=30, seed=1):
    rng = np.random.default_rng(seed)
    return [[float(v)] for v in rng.normal(10, 1, n)]

@pytest.mark.parametrize('method', ['Z_SCORE', 'IQR'])
def test_univariate_outliers(method):
    rows = normal_rows() + [[100.0]]
    outcome = run_job(job('OUTLIER_DETECTION', {'method': method}, [column(X)], rows))
    outliers = outcome.result['outliers']
    # ordered by score, IQR may also flag tails of the sample
    assert outliers[0]['value'] == 100.0
    assert outliers[0]['exclusion'] == {'unit_ids': [30], 'start': None, 'end': None, 'record_groups': None}
    assert outliers[0]['term'] == X

def test_mahalanobis_outlier():
    rng = np.random.default_rng(2)
    x = rng.normal(0, 1, 50)
    rows = [[float(a), float(a + rng.normal(0, 0.1))] for a in x] + [[2.0, -2.0]]
    outcome = run_job(job('OUTLIER_DETECTION', {'method': 'MAHALANOBIS'}, [column(X), column(Y)], rows))
    assert [o['observation']['unit_id'] for o in outcome.result['outliers']] == [50]
    assert outcome.result['outliers'][0]['term'] is None

def test_mahalanobis_insufficient_data():
    with pytest.raises(AnalysisJobFailed) as e:
        run_job(job('OUTLIER_DETECTION', {'method': 'MAHALANOBIS'}, [column(X), column(Y)], [[1.0, 2.0], [2.0, 1.0]]))
    assert e.value.errors[0].code == ErrorCode.INSUFFICIENT_DATA


@pytest.mark.parametrize('distance', ['EUCLIDEAN', 'MANHATTAN', 'MINKOWSKI'])
@pytest.mark.parametrize('clustering', [None, {'method': 'KMEANS', 'clusters': 2}, {'method': 'HIERARCHICAL', 'clusters': 2}])
def test_mds(distance, clustering):
    rng = np.random.default_rng(3)
    rows = [[float(v) for v in rng.normal(c, 0.1, 3)] for c in (0, 0, 0, 5, 5, 5)] + [[None, 1.0, 1.0]]
    columns = [column(X), column(Y), column(Z)]
    outcome = run_job(job('MDS', {'distance': distance, 'dimensions': 2, 'clustering': clustering}, columns, rows))
    observations = outcome.result['observations']
    # incomplete observations are not represented
    assert len(observations) == 6
    assert all(len(o['coordinates']) == 2 for o in observations)
    if clustering:
        clusters = [o['cluster_id'] for o in observations]
        assert clusters[0] == clusters[1] == clusters[2] != clusters[3] == clusters[4] == clusters[5]
    else:
        assert all(o['cluster_id'] is None for o in observations)
