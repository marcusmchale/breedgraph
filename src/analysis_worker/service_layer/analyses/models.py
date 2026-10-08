"""
ANOVA and estimated marginal means, fitted in R.

Models with only fixed terms are fitted with lm, models with any RANDOM term with lmer (lmerTest).
"""
import pandas as pd

from analysis_worker.adapters.r.models import to_r_frame, fit_anova, estimated_means, RError
from analysis_worker.domain.model.job import (
    AnalysisJob, AnalysisOutcome, AnalysisJobFailed, Message, ErrorCode, WarningCode, same_reference
)
from analysis_worker.service_layer.analyses.checks import (
    require_rows, single_level_columns, single_level_messages, term_level, insufficient
)

CONTRASTS = {'PAIRWISE': 'pairwise', 'TRT_VS_CTRL': 'trt.vs.ctrl', 'NONE': 'none'}
ADJUSTMENTS = {'TUKEY': 'tukey', 'BONFERRONI': 'bonferroni', 'HOLM': 'holm', 'SIDAK': 'sidak', 'NONE': 'none'}
DDF = {'SATTERTHWAITE': 'Satterthwaite', 'KENWARD_ROGER': 'Kenward-Roger'}


def _none_if_nan(value):
    return None if value is None or pd.isna(value) else float(value)


class ModelFrame:
    """Complete observations of the model columns, with R-safe column names."""

    def __init__(self, job: AnalysisJob, references: list[dict]):
        self.job = job
        self.columns = [job.column(r) for r in references]
        # trailing underscore so that no name is a prefix of another, e.g. for factor coefficients
        self.names = {c['name']: f"t{i}_" for i, c in enumerate(self.columns)}
        frame = job.frame()[[c['name'] for c in self.columns]].dropna()
        for column in self.columns:
            if column['kind'] != 'CONTINUOUS':
                frame[column['name']] = frame[column['name']].cat.remove_unused_categories()
        self.frame = frame

    def name(self, reference: dict) -> str:
        return self.names[self.job.column(reference)['name']]

    def reference(self, r_name: str) -> dict:
        """Term reference of an R column, or of a coefficient named after it"""
        matches = [c for c in self.columns if r_name.startswith(self.names[c['name']])]
        return max(matches, key=lambda c: len(self.names[c['name']]))['term']

    def column_by_r_name(self, r_name: str) -> dict:
        return next(c for c in self.columns if self.names[c['name']] == r_name)

    def r_data(self):
        renamed = self.frame.rename(columns=self.names)
        return to_r_frame(renamed, {self.names[c['name']]: c['kind'] for c in self.columns})

    def check(self, minimum: int, description: str):
        require_rows(self.frame, minimum, self.job, description)
        single = single_level_columns(self.frame, [c for c in self.columns if c['kind'] != 'CONTINUOUS'])
        if single:
            raise AnalysisJobFailed(single_level_messages(self.job, single, ErrorCode.SINGLE_LEVEL_TERM))


def _model_failed(job: AnalysisJob, error: Exception) -> AnalysisJobFailed:
    return AnalysisJobFailed([Message(code=ErrorCode.MODEL_FAILED, message=f"Model fitting failed: {error}", path=job.spec_path)])


def _not_converged(job: AnalysisJob, messages: list[str]) -> list[Message]:
    return [Message(code=WarningCode.MODEL_NOT_CONVERGED, message=m, path=job.spec_path) for m in messages]


""" Estimated marginal means """
def _estimated_means(
        job: AnalysisJob,
        model_frame: ModelFrame,
        model,
        spec: dict,
        alpha: float,
        ddf: str,
        response: dict | None
) -> dict:
    specs = [model_frame.name(r) for r in spec['terms']]
    by = [model_frame.name(r) for r in spec['by']]
    contrast = CONTRASTS[spec['contrast']]
    ref = 1
    if contrast == 'trt.vs.ctrl':
        column = model_frame.column_by_r_name(specs[0])
        levels = list(model_frame.frame[column['name']].cat.categories)
        if spec['control'] not in levels:
            raise AnalysisJobFailed([Message(
                code=ErrorCode.MODEL_FAILED,
                message=f"Control level '{spec['control']}' is not a level of the analysed observations",
                path=job.spec_path + ['estimatedMeans']
            )])
        ref = levels.index(spec['control']) + 1

    estimates = estimated_means(
        model, specs, by, contrast, ref, ADJUSTMENTS[spec['adjustment']], 1 - alpha, DDF.get(ddf, 'Satterthwaite')
    )
    means = estimates['means']
    lower, upper = _bounds(means)

    def levels_of(row, names):
        return [term_level(model_frame.column_by_r_name(n), row[n]) for n in names]

    mean_results = [
        {
            'levels': levels_of(row, specs),
            'by': levels_of(row, by),
            'mean': _none_if_nan(row['emmean']),
            'standard_error': _none_if_nan(row['SE']),
            'degrees_of_freedom': _none_if_nan(row.get('df')),
            'lower_confidence_limit': _none_if_nan(row[lower]),
            'upper_confidence_limit': _none_if_nan(row[upper]),
        }
        for _, row in means.iterrows()
    ]

    contrast_results = []
    if estimates['contrasts'] is not None:
        contrast_results = _contrasts(estimates['contrasts'], means, specs, by, contrast, ref, levels_of, alpha)

    return {
        'response': response,
        'terms': spec['terms'],
        'by': spec['by'],
        'contrast': spec['contrast'],
        'adjustment': spec['adjustment'],
        'means': mean_results,
        'contrasts': contrast_results
    }


def _bounds(frame: pd.DataFrame) -> tuple[str, str]:
    lower = next(c for c in frame.columns if c in ('lower.CL', 'asymp.LCL'))
    upper = next(c for c in frame.columns if c in ('upper.CL', 'asymp.UCL'))
    return lower, upper


def _contrasts(contrasts: pd.DataFrame, means: pd.DataFrame, specs, by, contrast, ref, levels_of, alpha) -> list[dict]:
    """
    Levels of each contrast are taken from the means grid of its by-group, in the order emmeans generates them:
    pairwise compares i - j for i < j, trt.vs.ctrl compares each other level with the control.
    """
    lower, upper = _bounds(contrasts)
    statistic = next(c for c in contrasts.columns if c in ('t.ratio', 'z.ratio'))
    by_key = (lambda row: tuple(str(row[n]) for n in by))
    groups: dict[tuple, list] = {}
    for _, row in means.iterrows():
        groups.setdefault(by_key(row), []).append(row)
    pairs = {}
    for key, rows in groups.items():
        if contrast == 'pairwise':
            pairs[key] = [(rows[i], rows[j]) for i in range(len(rows)) for j in range(i + 1, len(rows))]
        else:
            pairs[key] = [(rows[k], rows[ref - 1]) for k in range(len(rows)) if k != ref - 1]

    results = []
    position: dict[tuple, int] = {}
    for _, row in contrasts.iterrows():
        key = by_key(row)
        i = position.get(key, 0)
        position[key] = i + 1
        a, b = pairs[key][i]
        p = _none_if_nan(row['p.value'])
        results.append({
            'label': str(row['contrast']),
            'levels_a': levels_of(a, specs),
            'levels_b': levels_of(b, specs),
            'by': levels_of(row, by),
            'estimate': _none_if_nan(row['estimate']),
            'standard_error': _none_if_nan(row['SE']),
            'degrees_of_freedom': _none_if_nan(row.get('df')),
            'statistic': _none_if_nan(row[statistic]),
            'p_value': p,
            'lower_confidence_limit': _none_if_nan(row[lower]),
            'upper_confidence_limit': _none_if_nan(row[upper]),
            'significant': p < alpha if p is not None else None
        })
    return results


""" ANOVA """
def _formula(job: AnalysisJob, model_frame: ModelFrame) -> tuple[str, bool]:
    config = job.config
    model_terms = [t for t in config['terms'] if not same_reference(t['reference'], config['response'])]
    fixed = [model_frame.name(t['reference']) for t in model_terms if t['effect'] != 'RANDOM']
    fixed += [':'.join(model_frame.name(r) for r in i['terms']) for i in config['interactions']]
    random = []
    for term in model_terms:
        if term['effect'] != 'RANDOM':
            continue
        column = job.column(term['reference'])
        if column['kind'] == 'CONTINUOUS':
            raise AnalysisJobFailed([Message(
                code=ErrorCode.MODEL_FAILED,
                message="RANDOM terms must be categorical",
                path=job.term_path(term['reference']) + ['effect']
            )])
        slopes = ''.join(f" + {model_frame.name(s)}" for s in term['random_slope_terms'])
        random.append(f"(1{slopes} | {model_frame.name(term['reference'])})")
    rhs = ' + '.join(fixed + random) or '1'
    return f"{model_frame.name(config['response'])} ~ {rhs}", bool(random)


def anova(job: AnalysisJob) -> AnalysisOutcome:
    config = job.config
    model_frame = ModelFrame(job, [t['reference'] for t in config['terms']])
    model_frame.check(3, "ANOVA")
    formula, mixed = _formula(job, model_frame)
    ss_type = 3 if config['sum_of_squares'] == 'TYPE_III' else 2

    try:
        fit = fit_anova(model_frame.r_data(), formula, mixed, ss_type, DDF[config['ddf']])
    except RError as e:
        raise _model_failed(job, e)
    warnings = _not_converged(job, fit['warnings'])

    terms, interactions = [], []
    for _, row in fit['table'].iterrows():
        references = [model_frame.reference(name) for name in row['term'].split(':')]
        statistics = {
            'degrees_of_freedom': _none_if_nan(row['df']),
            'denominator_degrees_of_freedom': _none_if_nan(row['den_df']),
            'sum_of_squares': _none_if_nan(row['ss']),
            'mean_square': _none_if_nan(row['ms']),
            'f_statistic': _none_if_nan(row['f']),
            'p_value': _none_if_nan(row['p']),
        }
        if len(references) == 1:
            terms.append({'term': references[0], **statistics})
        else:
            interactions.append({'terms': references, **statistics})

    random_effects = [
        {
            'group': model_frame.reference(row['group']),
            'slope': model_frame.reference(row['slope']) if isinstance(row['slope'], str) else None,
            'variance': _none_if_nan(row['variance']),
            'standard_deviation': _none_if_nan(row['sd']),
        }
        for _, row in fit['random'].iterrows()
    ]

    residual = None
    if not mixed:
        row = fit['residual'].iloc[0]
        residual = {
            'degrees_of_freedom': _none_if_nan(row['df']),
            'sum_of_squares': _none_if_nan(row['ss']),
            'mean_square': _none_if_nan(row['ms']),
        }

    try:
        means = [
            _estimated_means(job, model_frame, fit['model'], spec, config['alpha'], config['ddf'], config['response'])
            for spec in config['estimated_means']
        ]
    except RError as e:
        raise _model_failed(job, e)

    return AnalysisOutcome(result={
        'terms': terms,
        'interactions': interactions,
        'random_effects': random_effects,
        'estimated_means': means,
        'residual': residual
    }, warnings=warnings)


""" Descriptive statistics """
def descriptive_estimated_means(job: AnalysisJob, frame: pd.DataFrame) -> tuple[list[dict], list[Message]]:
    """
    Least-squares means of each CONTINUOUS concept term, from a linear model
    of the categorical terms and the configured interactions.
    """
    config = job.config
    categorical = [c['term'] for c in job.columns_of_kind('CATEGORICAL', 'ORDINAL')]
    results, warnings = [], []
    for response in job.concept_columns('CONTINUOUS'):
        model_frame = ModelFrame(job, [response['term']] + categorical)
        try:
            model_frame.check(3, "Estimated means")
        except AnalysisJobFailed as e:
            # reported per response, other responses may still be estimated
            warnings += [Message(code=WarningCode.SINGLE_LEVEL_TERM, message=m.message, path=m.path)
                         for m in e.errors if m.code == ErrorCode.SINGLE_LEVEL_TERM]
            if not any(m.code == ErrorCode.SINGLE_LEVEL_TERM for m in e.errors):
                raise
            continue
        terms = [model_frame.name(r) for r in categorical]
        terms += [':'.join(model_frame.name(r) for r in i['terms']) for i in config.get('interactions') or []]
        formula = f"{model_frame.name(response['term'])} ~ {' + '.join(terms) or '1'}"
        try:
            fit = fit_anova(model_frame.r_data(), formula, False, 2, 'Satterthwaite')
            warnings += _not_converged(job, fit['warnings'])
            results += [
                _estimated_means(job, model_frame, fit['model'], spec, 0.05, 'SATTERTHWAITE', response['term'])
                for spec in config['estimated_means']
            ]
        except RError as e:
            raise _model_failed(job, e)
    if not results and not warnings:
        raise insufficient("No terms are suitable for estimated means", job.spec_path + ['estimatedMeans'])
    return results, warnings
