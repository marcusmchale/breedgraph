from typing import List
from src.breedgraph.domain.commands import Command
from pydantic import BaseModel
from src.breedgraph.domain.model.ontology.enums import ScaleType, ObservationMethodType, AxisType, VersionChange

class CommitOntologyVersion(Command):
    agent_id: int

    version_change: VersionChange = VersionChange.PATCH
    comment: str = ''
    licence: int|None = None
    copyright: int|None = None

class CreateEntryBase(BaseModel):
    agent_id: int

    name: str
    abbreviation: str | None = None
    synonyms: List[str] | None = None
    description: str | None = None

    author_ids: List[int] | None = None
    reference_ids: List[int] | None = None
    parent_ids: List[int] | None = None
    child_ids: List[int] | None = None

class CreateTerm(Command, CreateEntryBase):
    subject_ids: List[int] | None = None
    scale_ids: List[int] | None = None
    category_ids: List[int] | None = None
    observation_method_ids: List[int] | None = None
    trait_ids: List[int] | None = None
    variable_ids: List[int] | None = None
    control_method_ids: List[int] | None = None
    condition_ids: List[int] | None = None
    factor_ids: List[int] | None = None
    event_ids: List[int] | None = None
    location_type_ids: List[int] | None = None
    layout_type_ids: List[int] | None = None
    design_ids: List[int] | None = None
    role_ids: List[int] | None = None
    title_ids: List[int] | None = None

class CreateSubject(Command, CreateEntryBase):
    term_ids: List[int] | None = None

class CreateTrait(Command, CreateEntryBase):
    term_ids: List[int] | None = None
    subject_ids: List[int] = None

class CreateCondition(Command, CreateEntryBase):
    term_ids: List[int] | None = None
    subject_ids: List[int] = None

class CreateExposure(Command, CreateEntryBase):
    term_ids: List[int] | None = None
    subject_ids: List[int] = None

class CreateScale(Command, CreateEntryBase):
    scale_type: ScaleType
    term_ids: List[int] | None = None

class CreateScaleCategory(Command, CreateEntryBase):
    term_ids: List[int] | None = None

class CreateObservationMethod(Command, CreateEntryBase):
    observation_type: ObservationMethodType
    term_ids: List[int] | None = None

class CreateVariable(Command, CreateEntryBase):
    trait_id: int
    observation_method_id: int
    scale_id: int
    term_ids: List[int] | None = None

class CreateControlMethod(Command, CreateEntryBase):
    term_ids: List[int] | None = None

class CreateFactor(Command, CreateEntryBase):
    condition_id: int
    control_method_id: int
    scale_id: int
    term_ids: List[int] | None = None

class CreateEventType(Command, CreateEntryBase):
    variable_ids: List[int] = None
    factor_ids: List[int] = None
    term_ids: List[int] | None = None

class CreateLocationType(Command, CreateEntryBase):
    term_ids: List[int] | None = None

class CreateDesign(Command, CreateEntryBase):
    term_ids: List[int] | None = None

class CreateLayoutType(Command, CreateEntryBase):
    axes: List[AxisType]
    term_ids: List[int] | None = None