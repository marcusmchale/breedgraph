"""
Outlier detection. Thresholds are fixed:
Z_SCORE |z| > 3; IQR outside 1.5 IQR of the quartiles; MAHALANOBIS squared distance with chi-squared p < 0.001.
"""
import numpy as np
import pandas as pd
from scipy.stats import chi2

from analysis_worker.domain.model.job import AnalysisJob, AnalysisOutcome
from analysis_worker.service_layer.analyses.checks import insufficient

Z_THRESHOLD = 3.0
IQR_FACTOR = 1.5
MAHALANOBIS_P = 0.001


def _outlier(job: AnalysisJob, index: int, term: dict | None, value, score) -> dict:
    observation = job.observations[index]
    return {
        'observation': observation['group'],
        'exclusion': observation['exclusion'],
        'term': term,
        'value': None if value is None else float(value),
        'score': float(score)
    }


def _univariate(job: AnalysisJob, frame: pd.DataFrame, columns: list[dict], method: str) -> list[dict]:
    outliers = []
    for column in columns:
        values = frame[column['name']].dropna()
        if values.size < 3:
            continue
        if method == 'Z_SCORE':
            sd = values.std(ddof=1)
            if not sd > 0:
                continue
            scores = (values - values.mean()) / sd
            flagged = scores[scores.abs() > Z_THRESHOLD]
        else:
            q1, q3 = values.quantile(0.25), values.quantile(0.75)
            iqr = q3 - q1
            if not iqr > 0:
                continue
            # distance beyond the nearest quartile, in IQR units
            scores = np.maximum(q1 - values, values - q3) / iqr
            flagged = scores[scores > IQR_FACTOR]
        outliers += [_outlier(job, int(i), column['term'], values[i], s) for i, s in flagged.items()]
    return outliers


def _mahalanobis(job: AnalysisJob, frame: pd.DataFrame, columns: list[dict]) -> list[dict]:
    data = frame[[c['name'] for c in columns]].dropna()
    n, p = data.shape
    if n <= p + 1:
        raise insufficient(
            f"Mahalanobis distance requires more than {p + 1} complete observations, {n} available",
            job.spec_path + ['terms']
        )
    centred = data - data.mean()
    precision = np.linalg.pinv(np.cov(centred.to_numpy(), rowvar=False).reshape(p, p))
    distances = np.einsum('ij,jk,ik->i', centred.to_numpy(), precision, centred.to_numpy())
    threshold = chi2.ppf(1 - MAHALANOBIS_P, df=p)
    return [
        _outlier(job, int(i), None, None, d)
        for i, d in zip(data.index, distances) if d > threshold
    ]


def outlier_detection(job: AnalysisJob) -> AnalysisOutcome:
    frame = job.frame()
    columns = job.concept_columns('CONTINUOUS')
    method = job.config['method']
    if method == 'MAHALANOBIS':
        outliers = _mahalanobis(job, frame, columns)
    else:
        outliers = _univariate(job, frame, columns, method)
    outliers.sort(key=lambda o: -o['score'])
    return AnalysisOutcome(result={'outliers': outliers})
