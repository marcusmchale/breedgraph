"""
Descriptive statistics of each CONTINUOUS concept term, and a summary of each ORDINAL concept term as its ranked
categories allow, overall and for each combination of levels of the CATEGORICAL and ORDINAL terms (an ORDINAL term's
own levels left out of the groups of its summary).
"""
import numpy as np
import pandas as pd

from analysis_worker.domain.model.job import AnalysisJob, AnalysisOutcome, WarningCode
from analysis_worker.service_layer.analyses.checks import single_level_columns, single_level_messages, term_level

# the AnalysisGroup fields of each domain term type
GROUP_FIELDS = {
    'TIME': 'time', 'GERMPLASM': 'germplasm_id', 'UNIT': 'unit_id', 'LOCATION': 'location_id', 'STUDY': 'study_id'
}


def _statistics(values: pd.Series) -> dict:
    present = values.dropna()
    count = int(present.size)
    if count == 0:
        return {'count': 0, 'missing_count': int(values.size)}
    sd = float(present.std(ddof=1)) if count > 1 else None
    return {
        'count': count,
        'missing_count': int(values.size - count),
        'mean': float(present.mean()),
        'standard_deviation': sd,
        'standard_error': sd / np.sqrt(count) if sd is not None else None,
        'median': float(present.median()),
        'minimum': float(present.min()),
        'maximum': float(present.max()),
        'lower_quartile': float(present.quantile(0.25)),
        'upper_quartile': float(present.quantile(0.75)),
    }


def _quantile(codes: np.ndarray, q: float) -> int:
    """The category, by its rank, at a quantile: the first whose cumulative share reaches it, so always one observed"""
    return int(np.quantile(codes, q, method='inverted_cdf'))


def _ordinal_summary(values: pd.Series) -> dict:
    """
    An ordinal term's observations, e.g. disease scores: how many fell in each category, in the scale's order, with
    their share of those observed, and the minimum, quartiles, median and maximum, each a category. No mean or
    standard deviation, which would take the steps between categories as equal.
    """
    present = values.dropna()
    count = int(present.size)
    levels = list(values.cat.categories)
    counts = present.value_counts(sort=False).reindex(levels, fill_value=0)
    ordinal = {
        'categories': [
            {'level': str(level), 'count': int(n), 'share': float(n / count) if count else None}
            for level, n in counts.items()
        ],
        **{name: None for name in ('minimum', 'lower_quartile', 'median', 'upper_quartile', 'maximum')}
    }
    if count:
        codes = present.cat.codes.to_numpy()
        for name, q in (('minimum', 0), ('lower_quartile', 0.25), ('median', 0.5), ('upper_quartile', 0.75), ('maximum', 1)):
            ordinal[name] = str(levels[_quantile(codes, q)])
    return {'count': count, 'missing_count': int(values.size - count), 'ordinal': ordinal}


def _group(job: AnalysisJob, columns: list[dict], index: int) -> dict | None:
    """The AnalysisGroup of a combination of domain term levels, from a member observation."""
    if not columns or any(c['term']['type'] == 'CONCEPT' for c in columns):
        return None
    observation = job.observations[index]['group']
    group = {field: None for field in GROUP_FIELDS.values()} | {'record_groups': [], 'layout_axes': []}
    for column in columns:
        term = column['term']
        if term['type'] == 'RECORD_GROUP':
            group['record_groups'] += [
                a for a in observation['record_groups'] if a['dimension'] == term['record_group_dimension']
            ]
        elif term['type'] == 'LAYOUT_AXIS':
            group['layout_axes'] += [a for a in observation['layout_axes'] if a['axis'] == term['layout_axis']]
        else:
            field = GROUP_FIELDS[term['type']]
            group[field] = observation[field]
    return group


def descriptive_statistics(job: AnalysisJob) -> AnalysisOutcome:
    frame = job.frame()
    grouping = job.columns_of_kind('CATEGORICAL', 'ORDINAL')
    warnings = single_level_messages(job, single_level_columns(frame, grouping), WarningCode.SINGLE_LEVEL_TERM)
    # the terms described, in the order given: statistics of the continuous, summaries of the ordinal
    described = [
        (column, _statistics if column['kind'] == 'CONTINUOUS' else _ordinal_summary)
        for column in job.concept_columns('CONTINUOUS', 'ORDINAL')
    ]

    results = []
    for column, describe in described:
        values = frame[column['name']]
        results.append({'term': column['term'], 'levels': [], 'group': None, **describe(values)})
        groups = [c for c in grouping if c['name'] != column['name']]
        if not groups:
            continue
        names = [c['name'] for c in groups]
        for key, members in frame.groupby(names, observed=True, sort=True):
            key = key if isinstance(key, tuple) else (key,)
            results.append({
                'term': column['term'],
                'levels': [term_level(c, level) for c, level in zip(groups, key)],
                'group': _group(job, groups, int(members.index[0])),
                **describe(values.loc[members.index])
            })

    estimated_means = []
    if job.config.get('estimated_means'):
        # least-squares means require a fitted model
        from analysis_worker.service_layer.analyses.models import descriptive_estimated_means
        estimated_means, model_warnings = descriptive_estimated_means(job, frame)
        warnings += model_warnings

    return AnalysisOutcome(result={'terms': results, 'estimated_means': estimated_means}, warnings=warnings)
