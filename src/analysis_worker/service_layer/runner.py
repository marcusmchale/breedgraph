"""
Runs an analysis job. Analyses are dispatched by analysis_type.

Model fitting, ANOVA tables and post-hoc comparisons will run in R via pymer4;
descriptive statistics, correlation, MDS, clustering and outlier detection in Python.
"""
from typing import Callable

from analysis_worker.domain.model.job import AnalysisJob, AnalysisOutcome, AnalysisJobFailed, Message, ErrorCode


def _anova(job: AnalysisJob) -> AnalysisOutcome:
    # R is only loaded when required
    from analysis_worker.service_layer.analyses.models import anova
    return anova(job)

def _descriptive(job: AnalysisJob) -> AnalysisOutcome:
    from analysis_worker.service_layer.analyses.descriptive import descriptive_statistics
    return descriptive_statistics(job)

def _correlation(job: AnalysisJob) -> AnalysisOutcome:
    from analysis_worker.service_layer.analyses.correlation import correlation
    return correlation(job)

def _outliers(job: AnalysisJob) -> AnalysisOutcome:
    from analysis_worker.service_layer.analyses.outliers import outlier_detection
    return outlier_detection(job)

def _mds(job: AnalysisJob) -> AnalysisOutcome:
    from analysis_worker.service_layer.analyses.mds import mds
    return mds(job)


ANALYSES: dict[str, Callable[[AnalysisJob], AnalysisOutcome]] = {
    'ANOVA': _anova,
    'MDS': _mds,
    'CORRELATION': _correlation,
    'DESCRIPTIVE_STATISTICS': _descriptive,
    'OUTLIER_DETECTION': _outliers,
}


def run_job(job: AnalysisJob) -> AnalysisOutcome:
    """
    :raises AnalysisJobFailed: with the errors to report
    """
    analysis = ANALYSES.get(job.analysis_type)
    if analysis is None:
        raise AnalysisJobFailed([Message(
            code=ErrorCode.INTERNAL_ERROR, message=f"Unknown analysis type {job.analysis_type}"
        )])
    return analysis(job)
