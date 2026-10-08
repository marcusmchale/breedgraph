import pandas as pd

from analysis_worker.domain.model.job import AnalysisJob, AnalysisJobFailed, Message, ErrorCode, WarningCode


def insufficient(message: str, path: list[str] | None = None) -> AnalysisJobFailed:
    return AnalysisJobFailed([Message(code=ErrorCode.INSUFFICIENT_DATA, message=message, path=path)])


def require_rows(frame: pd.DataFrame, minimum: int, job: AnalysisJob, description: str):
    if len(frame) < minimum:
        raise insufficient(
            f"{description} requires at least {minimum} complete observations, {len(frame)} available",
            job.spec_path + ['terms']
        )


def single_level_columns(frame: pd.DataFrame, columns: list[dict]) -> list[dict]:
    """Categorical columns with fewer than two observed levels"""
    return [c for c in columns if frame[c['name']].dropna().nunique() < 2]


def single_level_messages(job: AnalysisJob, columns: list[dict], code: ErrorCode | WarningCode) -> list[Message]:
    return [
        Message(
            code=code,
            message=f"Term {column['name']} has fewer than two levels in the analysed observations",
            path=job.term_path(column['term'])
        )
        for column in columns
    ]


def term_level(column: dict, level) -> dict:
    return {'term': column['term'], 'level': str(level)}
