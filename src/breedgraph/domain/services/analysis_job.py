"""
The job payload sent to the analysis worker, and the format of its replies.

The worker receives only this payload: the observation frame and the analysis configuration.
Keys are snake_case. NaN and infinite values are written as null.
"""
import math
from dataclasses import asdict, is_dataclass
from enum import Enum

import numpy as np

from breedgraph.domain.model.analysis import AnalysisRequest
from breedgraph.domain.services.observation_builder import ObservationFrame

JOB_FORMAT_VERSION = 1


def to_jsonable(value):
    """Convert to JSON compatible values: enums by value, datetimes as ISO strings, NaN/inf as null."""
    if is_dataclass(value) and not isinstance(value, type):
        return to_jsonable(asdict(value))
    if isinstance(value, dict):
        return {str(k): to_jsonable(v) for k, v in value.items()}
    if isinstance(value, (list, tuple, set, frozenset)):
        return [to_jsonable(v) for v in value]
    if isinstance(value, Enum):
        return value.value
    if isinstance(value, np.datetime64):
        return None if np.isnat(value) else str(value)
    if isinstance(value, np.generic):
        value = value.item()
    if isinstance(value, float) and not math.isfinite(value):
        return None
    return value


def build_job_payload(analysis_id: str, request: AnalysisRequest, frame: ObservationFrame) -> dict:
    """
    rows are aligned with observations; each row holds values in the order of columns.
    """
    data = frame.data.astype(object).where(frame.data.notna(), None)
    return to_jsonable({
        'version': JOB_FORMAT_VERSION,
        'analysis_id': analysis_id,
        'analysis_type': request.analysis_type,
        'config': request.spec,
        'columns': [
            {'name': c.name, 'term': c.reference.model_dump(), 'kind': c.kind, 'levels': c.levels}
            for c in frame.columns
        ],
        'rows': data.values.tolist(),
        'observations': [
            {
                'group': o.group,
                'record_ids': o.record_ids,
                'unit_ids': o.unit_ids,
                'exclusion': o.exclusion
            }
            for o in frame.observations
        ]
    })
