"""
The analysis job as received from the web server, and the outcome reported back.

Mirrors the payload format of breedgraph.domain.services.analysis_job.
"""
from dataclasses import dataclass, field
from enum import Enum

import pandas as pd


class ErrorCode(str, Enum):
    INSUFFICIENT_DATA = "INSUFFICIENT_DATA"
    SINGLE_LEVEL_TERM = "SINGLE_LEVEL_TERM"
    MODEL_FAILED = "MODEL_FAILED"
    INTERNAL_ERROR = "INTERNAL_ERROR"

class WarningCode(str, Enum):
    SINGLE_LEVEL_TERM = "SINGLE_LEVEL_TERM"
    MODEL_NOT_CONVERGED = "MODEL_NOT_CONVERGED"


@dataclass
class Message:
    code: ErrorCode | WarningCode
    message: str
    path: list[str] | None = None
    record_ids: list[int] | None = None

    def model_dump(self) -> dict:
        return {'code': self.code.value, 'message': self.message, 'path': self.path, 'record_ids': self.record_ids}


class AnalysisJobFailed(Exception):
    def __init__(self, errors: list[Message], warnings: list[Message] | None = None):
        self.errors = errors
        self.warnings = warnings or []
        super().__init__("; ".join(e.message for e in errors))


@dataclass
class AnalysisJob:
    analysis_id: str
    lease: str
    lease_seconds: int
    payload: dict

    @property
    def analysis_type(self) -> str:
        return self.payload['analysis_type']

    @property
    def config(self) -> dict:
        return self.payload['config']

    @property
    def columns(self) -> list[dict]:
        return self.payload['columns']

    @property
    def observations(self) -> list[dict]:
        """Observation metadata, aligned with the rows of the frame"""
        return self.payload['observations']

    @property
    def spec_path(self) -> list[str]:
        """Input path of the analysis configuration, for messages"""
        head, *tail = self.analysis_type.lower().split('_')
        return [head + ''.join(part.title() for part in tail)]

    def column(self, reference: dict) -> dict:
        """The column of a term reference"""
        for column in self.columns:
            if same_reference(column['term'], reference):
                return column
        raise KeyError(f"No column for term {reference}")

    def term_path(self, reference: dict) -> list[str]:
        for i, term in enumerate(self.config['terms']):
            if same_reference(term['reference'], reference):
                return self.spec_path + ['terms', str(i)]
        return self.spec_path + ['terms']

    def columns_of_kind(self, *kinds: str) -> list[dict]:
        return [c for c in self.columns if c['kind'] in kinds]

    def concept_columns(self, *kinds: str) -> list[dict]:
        return [c for c in self.columns_of_kind(*kinds) if c['term']['type'] == 'CONCEPT']

    def frame(self) -> pd.DataFrame:
        """One row per observation, one column per term; CATEGORICAL and ORDINAL columns are pandas categoricals."""
        frame = pd.DataFrame(self.payload['rows'], columns=[c['name'] for c in self.columns])
        for column in self.columns:
            name = column['name']
            if column['kind'] == 'CONTINUOUS':
                frame[name] = pd.to_numeric(frame[name])
            else:
                frame[name] = pd.Categorical(
                    frame[name], categories=column['levels'], ordered=column['kind'] == 'ORDINAL'
                )
        return frame


def same_reference(a: dict, b: dict) -> bool:
    return all(a.get(k) == b.get(k) for k in ('type', 'concept_id', 'record_group_dimension'))


def record_ids(observations: list[dict], indexes) -> list[int]:
    """Records contributing to the observations at the given indexes"""
    return sorted({r for i in indexes for r in observations[i]['record_ids']})


@dataclass
class AnalysisOutcome:
    result: dict
    warnings: list[Message] = field(default_factory=list)
