from dataclasses import dataclass, asdict
from enum import Enum
from numpy import datetime64

from .ontology.variables import ScaleBase, ScaleType

class AnalysisTreatment(Enum):
    CONTINUOUS = 'continuous'
    CATEGORICAL = 'categorical'

class AnalysisVariableType(Enum):
    CONCEPT = 'concept'
    GERMPLASM = 'germplasm'
    TIMEPOINT = 'timepoint'

from typing import List, Tuple

@dataclass
class AnalysisVariable:
    label: str  # used for display, comes from front end, e.g. timepoint in days, germplasm as variety etc.
    type: AnalysisVariableType
    scale: ScaleBase
    treatment: AnalysisTreatment
    concept_id: int | None

    def __post_init__(self):
        if self.type == AnalysisVariableType.CONCEPT and self.concept_id is None:
            raise ValueError("Concept ID must be provided for concept variables")
        if self.type == AnalysisVariableType.GERMPLASM and self.concept_id is not None:
            raise ValueError("Concept ID should not be provided for germplasm variables")

@dataclass
class AnalysisConfig:
    name: str
    dataset_ids: List[int]
    dependent_variable: AnalysisVariable
    independent_variables: List[AnalysisVariable]
    interaction_terms: List[Tuple[int, int]]  # indices in independent variables list
    timepoint_boundaries: List[datetime64]

    def __post_init__(self):
        if not self.dependent_variable.type == AnalysisVariableType.CONCEPT:
            raise ValueError('Dependent variable must be concept')
        for t in self.interaction_terms:
            if not t[0] in self.independent_variables and t[1] in self.independent_variables:
                raise ValueError('Interaction terms include variables that are not in independent variables')
        if self.timepoint_boundaries:
            for iv in self.independent_variables:
                if iv.type == AnalysisVariableType.TIMEPOINT:
                    break
            else:
                ValueError('Timepoint boundaries should only be set if timepoint variable is being estimated')

    def model_dump(self):
        return asdict(self)