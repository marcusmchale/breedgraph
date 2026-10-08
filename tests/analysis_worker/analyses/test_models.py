import itertools
import json
import shutil
import subprocess

import numpy as np
import pytest

pytest.importorskip("rpy2")

R_PACKAGES = ("lme4", "lmerTest", "emmeans", "car", "pbkrtest")

def _r_packages_installed() -> bool:
    if shutil.which("Rscript") is None:
        return False
    check = "cat(all(sapply(c(%s), requireNamespace, quietly=TRUE)))" % ",".join(f'"{p}"' for p in R_PACKAGES)
    result = subprocess.run(["Rscript", "-e", check], capture_output=True, text=True)
    return result.stdout.strip() == "TRUE"

pytestmark = pytest.mark.skipif(not _r_packages_installed(), reason="R packages for models are not installed")

from analysis_worker.domain.model.job import AnalysisJobFailed, ErrorCode
from analysis_worker.service_layer.runner import run_job

from .payloads import concept, domain, column, job, term

Y, A, B, X = concept(1), concept(2), concept(3), concept(4)
G = domain('GERMPLASM')


def anova_config(terms, interactions=(), estimated_means=(), sum_of_squares='TYPE_III', ddf='SATTERTHWAITE'):
    return {
        'terms': terms,
        'response': Y,
        'interactions': [{'terms': list(i)} for i in interactions],
        'alpha': 0.05,
        'sum_of_squares': sum_of_squares,
        'ddf': ddf,
        'estimated_means': list(estimated_means),
    }

def means_spec(terms, by=(), contrast='PAIRWISE', control=None, adjustment='TUKEY'):
    return {'terms': list(terms), 'by': list(by), 'contrast': contrast, 'control': control, 'adjustment': adjustment}


def balanced_two_way():
    rng = np.random.default_rng(4)
    rows = []
    for a, b in itertools.product(['a1', 'a2'], ['b1', 'b2']):
        effect = {'a1': 0, 'a2': 2}[a] + {'b1': 0, 'b2': 1}[b] + (1.5 if (a, b) == ('a2', 'b2') else 0)
        rows += [[float(effect + rng.normal()), a, b] for _ in range(3)]
    columns = [column(Y), column(A, 'CATEGORICAL', ['a1', 'a2']), column(B, 'CATEGORICAL', ['b1', 'b2'])]
    return columns, rows

def sums_of_squares(rows):
    y = np.array([r[0] for r in rows])
    grand = y.mean()
    def ss(index):
        groups = {}
        for row in rows:
            groups.setdefault(tuple(row[i] for i in index), []).append(row[0])
        return sum(len(v) * (np.mean(v) - grand) ** 2 for v in groups.values())
    cells = ss((1, 2))
    ss_a, ss_b = ss((1,)), ss((2,))
    return {'A': ss_a, 'B': ss_b, 'AB': cells - ss_a - ss_b, 'residual': float(((y - grand) ** 2).sum() - cells)}


@pytest.mark.parametrize('sum_of_squares', ['TYPE_II', 'TYPE_III'])
def test_lm_balanced_two_way(sum_of_squares):
    columns, rows = balanced_two_way()
    config = anova_config([term(Y), term(A), term(B)], interactions=[(A, B)], sum_of_squares=sum_of_squares)
    outcome = run_job(job('ANOVA', config, columns, rows))
    result = outcome.result
    expected = sums_of_squares(rows)
    terms = {r['term']['concept_id']: r for r in result['terms']}
    assert terms[2]['sum_of_squares'] == pytest.approx(expected['A'])
    assert terms[3]['sum_of_squares'] == pytest.approx(expected['B'])
    assert terms[2]['degrees_of_freedom'] == 1 and terms[2]['denominator_degrees_of_freedom'] is None
    interaction, = result['interactions']
    assert [t['concept_id'] for t in interaction['terms']] == [2, 3]
    assert interaction['sum_of_squares'] == pytest.approx(expected['AB'])
    assert result['residual']['sum_of_squares'] == pytest.approx(expected['residual'])
    assert result['residual']['degrees_of_freedom'] == 8
    assert result['random_effects'] == []
    json.dumps(result, allow_nan=False)


def mixed_rows(slope=False):
    rng = np.random.default_rng(5)
    rows = []
    for g in range(8):
        intercept, g_slope = rng.normal(0, 2), rng.normal(0, 0.5) if slope else 0
        for x in range(6):
            rows.append([float(intercept + (2 + g_slope) * x + rng.normal(0, 0.5)), float(x), str(g)])
    columns = [column(Y), column(X), column(G, 'CATEGORICAL', [str(g) for g in range(8)])]
    return columns, rows

@pytest.mark.parametrize('ddf', ['SATTERTHWAITE', 'KENWARD_ROGER'])
def test_lmer_random_intercept(ddf):
    columns, rows = mixed_rows()
    config = anova_config([term(Y), term(X), term(G, effect='RANDOM')], ddf=ddf)
    result = run_job(job('ANOVA', config, columns, rows)).result
    x, = result['terms']
    assert x['term'] == X
    assert x['p_value'] < 0.001
    assert 1 <= x['denominator_degrees_of_freedom'] <= len(rows)
    random, = result['random_effects']
    assert random['group'] == G and random['slope'] is None
    assert random['variance'] > 0 and random['standard_deviation'] == pytest.approx(np.sqrt(random['variance']))
    assert result['residual'] is None

def test_lmer_random_slope():
    columns, rows = mixed_rows(slope=True)
    config = anova_config([term(Y), term(X), term(G, effect='RANDOM', slopes=[X])])
    result = run_job(job('ANOVA', config, columns, rows)).result
    assert [(r['group'], r['slope']) for r in result['random_effects']] == [(G, None), (G, X)]


def one_way(levels=('a1', 'a2', 'a3')):
    rng = np.random.default_rng(6)
    rows = [[float(i * 2 + rng.normal(0, 0.3)), level] for i, level in enumerate(levels) for _ in range(4)]
    return [column(Y), column(A, 'CATEGORICAL', list(levels))], rows

def test_estimated_means_pairwise():
    columns, rows = one_way()
    config = anova_config([term(Y), term(A)], estimated_means=[means_spec([A])])
    means, = run_job(job('ANOVA', config, columns, rows)).result['estimated_means']
    assert means['response'] == Y
    assert [m['levels'][0]['level'] for m in means['means']] == ['a1', 'a2', 'a3']
    assert means['means'][1]['mean'] == pytest.approx(np.mean([r[0] for r in rows if r[1] == 'a2']))
    pairs = [(c['levels_a'][0]['level'], c['levels_b'][0]['level']) for c in means['contrasts']]
    assert pairs == [('a1', 'a2'), ('a1', 'a3'), ('a2', 'a3')]
    for contrast, (a, b) in zip(means['contrasts'], pairs):
        assert contrast['label'] == f"{a} - {b}"
        assert contrast['significant'] is True

def test_estimated_means_against_control():
    columns, rows = one_way()
    config = anova_config(
        [term(Y), term(A)],
        estimated_means=[means_spec([A], contrast='TRT_VS_CTRL', control='a2', adjustment='BONFERRONI')]
    )
    means, = run_job(job('ANOVA', config, columns, rows)).result['estimated_means']
    assert [(c['levels_a'][0]['level'], c['levels_b'][0]['level']) for c in means['contrasts']] == [('a1', 'a2'), ('a3', 'a2')]

def test_estimated_means_by():
    columns, rows = balanced_two_way()
    config = anova_config(
        [term(Y), term(A), term(B)], interactions=[(A, B)],
        estimated_means=[means_spec([A], by=[B], contrast='NONE')]
    )
    means, = run_job(job('ANOVA', config, columns, rows)).result['estimated_means']
    assert [(m['levels'][0]['level'], m['by'][0]['level']) for m in means['means']] == [
        ('a1', 'b1'), ('a2', 'b1'), ('a1', 'b2'), ('a2', 'b2')
    ]
    assert means['contrasts'] == []

def test_single_level_term_is_an_error():
    columns, rows = one_way(levels=('a1',))
    with pytest.raises(AnalysisJobFailed) as e:
        run_job(job('ANOVA', anova_config([term(Y), term(A)]), columns, rows))
    assert e.value.errors[0].code == ErrorCode.SINGLE_LEVEL_TERM
    assert e.value.errors[0].path == ['anova', 'terms', '1']


def test_descriptive_estimated_means():
    columns, rows = one_way()
    outcome = run_job(job(
        'DESCRIPTIVE_STATISTICS',
        {'interactions': [], 'estimated_means': [means_spec([A], contrast='NONE')]},
        columns, rows
    ))
    means, = outcome.result['estimated_means']
    assert means['response'] == Y
    assert len(means['means']) == 3


@pytest.mark.asyncio
async def test_worker_runs_r_analysis_in_process_pool():
    """As deployed: a fresh spawned process for each job, so embedded R runs on its main thread."""
    import multiprocessing
    from concurrent.futures import ProcessPoolExecutor
    from analysis_worker.service_layer.worker import AnalysisWorker
    from tests.analysis_worker.test_analysis_worker import MockAnalysisAPIClient

    columns, rows = one_way()
    client = MockAnalysisAPIClient([job('ANOVA', anova_config([term(Y), term(A)]), columns, rows)])
    with ProcessPoolExecutor(max_workers=1, mp_context=multiprocessing.get_context('spawn'), max_tasks_per_child=1) as executor:
        await AnalysisWorker(client, executor=executor).process_next()
    assert client.failures == []
    (_, result, _), = client.results
    assert result['terms'][0]['term'] == A
