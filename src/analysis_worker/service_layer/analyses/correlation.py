import pandas as pd

from analysis_worker.domain.model.job import AnalysisJob, AnalysisOutcome
from analysis_worker.service_layer.analyses.checks import insufficient


def correlation(job: AnalysisJob) -> AnalysisOutcome:
    frame = job.frame()
    columns = job.concept_columns('CONTINUOUS', 'ORDINAL')
    data = pd.DataFrame({
        # ordinal levels are correlated by rank of level
        c['name']: frame[c['name']].cat.codes.where(frame[c['name']].notna()) if c['kind'] == 'ORDINAL'
        else frame[c['name']]
        for c in columns
    })
    if data.dropna(how='all').shape[0] < 3:
        raise insufficient("Correlation requires at least 3 observations", job.spec_path + ['terms'])
    # pairwise complete observations
    matrix = data.corr(method=job.config['method'].lower(), min_periods=3)
    return AnalysisOutcome(result={
        'terms': [c['term'] for c in columns],
        'matrix': [
            {'term': c['term'], 'values': [None if pd.isna(v) else float(v) for v in matrix.loc[c['name']]]}
            for c in columns
        ]
    })
