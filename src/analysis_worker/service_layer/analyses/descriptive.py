"""
Descriptive statistics of each CONTINUOUS concept term, overall and for each
combination of levels of the CATEGORICAL and ORDINAL terms.
"""
import numpy as np
import pandas as pd

from analysis_worker.domain.model.job import AnalysisJob, AnalysisOutcome, WarningCode
from analysis_worker.service_layer.analyses.checks import single_level_columns, single_level_messages, term_level

# the AnalysisGroup fields of each domain term type
GROUP_FIELDS = {
    'TIME': 'time', 'GERMPLASM': 'germplasm_id', 'UNIT': 'unit_id', 'POSITION': 'position', 'STUDY': 'study_id'
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


def _group(job: AnalysisJob, columns: list[dict], index: int) -> dict | None:
    """The AnalysisGroup of a combination of domain term levels, from a member observation."""
    if not columns or any(c['term']['type'] == 'CONCEPT' for c in columns):
        return None
    observation = job.observations[index]['group']
    group = {field: None for field in GROUP_FIELDS.values()} | {'record_groups': []}
    for column in columns:
        term = column['term']
        if term['type'] == 'RECORD_GROUP':
            group['record_groups'] += [
                a for a in observation['record_groups'] if a['dimension'] == term['record_group_dimension']
            ]
        else:
            field = GROUP_FIELDS[term['type']]
            group[field] = observation[field]
    return group


def descriptive_statistics(job: AnalysisJob) -> AnalysisOutcome:
    frame = job.frame()
    continuous = job.concept_columns('CONTINUOUS')
    grouping = job.columns_of_kind('CATEGORICAL', 'ORDINAL')
    warnings = single_level_messages(job, single_level_columns(frame, grouping), WarningCode.SINGLE_LEVEL_TERM)

    results = []
    for column in continuous:
        values = frame[column['name']]
        results.append({'term': column['term'], 'levels': [], 'group': None, **_statistics(values)})
        if not grouping:
            continue
        names = [c['name'] for c in grouping]
        for key, members in frame.groupby(names, observed=True, sort=True):
            results.append({
                'term': column['term'],
                'levels': [term_level(c, level) for c, level in zip(grouping, key)],
                'group': _group(job, grouping, int(members.index[0])),
                **_statistics(values.loc[members.index])
            })

    estimated_means = []
    if job.config.get('estimated_means'):
        # least-squares means require a fitted model
        from analysis_worker.service_layer.analyses.models import descriptive_estimated_means
        estimated_means, model_warnings = descriptive_estimated_means(job, frame)
        warnings += model_warnings

    return AnalysisOutcome(result={'terms': results, 'estimated_means': estimated_means}, warnings=warnings)
