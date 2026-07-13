from pydantic import BaseModel, Field

from breedgraph.domain.model.time_descriptors import PyDT64
from breedgraph.domain.model.analysis import AnalysisVariableType

class AnalysisVariableImport(BaseModel):
    label: str
    type: AnalysisVariableType
    concept_id: int | None = None

class InteractionTermImport(BaseModel):
    var_1_index: int
    var_2_index: int

class AnalysisImport(BaseModel):
    name: str | None = None
    dataset_ids: list[int] = Field(default_factory=list)
    dependent_variable: AnalysisVariableImport
    independent_variables: list[AnalysisVariableImport] = Field(default_factory=list)
    interaction_terms: list[InteractionTermImport] = Field(default_factory=list)
    timepoint_boundaries: list[PyDT64] = Field(default_factory=list)
