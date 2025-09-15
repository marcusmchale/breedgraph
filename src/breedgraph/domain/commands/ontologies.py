from typing import List
from src.breedgraph.domain.commands import Command
from pydantic import BaseModel
from src.breedgraph.domain.model.ontology.enums import ScaleType, ObservationMethodType, AxisType

class CommitOntology(Command):
    user: int
    version_change: str = 'PATCH'
    comment: str = ''
    licence: int|None = None
    copyright: int|None = None

class CreateEntryBase(BaseModel):
    user: int
    name: str
    abbreviation: str | None = None
    synonyms: List[str] | None = None
    description: str | None = None
    authors: List[int] | None = None
    references: List[int] | None = None
    parents: List[int] | None = None
    children: List[int] | None = None

class CreateTerm(Command, CreateEntryBase):
    pass

class CreateSubject(Command, CreateEntryBase):
    pass

class CreateTrait(Command, CreateEntryBase):
    subjects: List[int] = None

class CreateCondition(Command, CreateEntryBase):
    subjects: List[int] = None

class CreateExposure(Command, CreateEntryBase):
    subjects: List[int] = None

class CreateScale(Command, CreateEntryBase):
    scale_type: ScaleType

class CreateScaleCategory(Command, CreateEntryBase):
    pass

class CreateObservationMethod(Command, CreateEntryBase):
    observation_type: ObservationMethodType

class CreateVariable(Command, CreateEntryBase):
    trait_id: int
    observation_method_id: int
    scale_id: int

class CreateControlMethod(Command, CreateEntryBase):
    pass

class CreateFactor(Command, CreateEntryBase):
    condition_id: int
    control_method_id: int
    scale_id: int

class CreateEventType(Command, CreateEntryBase):
    variables: List[int] = None
    factors: List[int] = None

class CreateGermplasmMethod(Command, CreateEntryBase):
    pass

class CreateLocationType(Command, CreateEntryBase):
    pass

class CreateDesign(Command, CreateEntryBase):
    pass

class CreateLayoutType(Command, CreateEntryBase):
    axes: List[AxisType]