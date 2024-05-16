import logging

from enum import Enum, IntEnum
from pydantic import BaseModel, Field, field_validator
from datetime import datetime

from src.breedgraph.domain.model.ontologies import (
    ConditionStored,
    SubjectStored,
    DesignStored,
    EventTypeStored,
    GermplasmStored, VariableStored
)
from src.breedgraph.domain.model.people import Person
from src.breedgraph.domain.model.locations import LocationStored
from src.breedgraph.domain.model.references import (
    Reference,
    IdentifiedReference,
    PublicationReference,
    DataReference,
    LegalReference
)

from src.breedgraph.adapters.repositories.base import Entity, Aggregate, AggregateRoot

from typing import List

logger = logging.getLogger(__name__)

class ObservationLevel(BaseModel):
    subject: SubjectStored = Field(frozen=True)
    order: int  # e.g. field = 1, plant = 6

class Study(BaseModel):
    """
    This is like the Study concept in BrAPI/ISA
    https://isa-specs.readthedocs.io/en/latest/isamodel.html
    """
    name: str

    fullname: str|None = None
    description: str|None = None
    external_id: str|None = None # an permanent external identifier, e.g. DOI

    location: LocationStored = Field(frozen=True)
    design: DesignStored = Field(frozen=True)
    germplasm: List[GermplasmStored]  # germplasm references
    variables: List[VariableStored] = Field(frozen=True)
    conditions: List[ConditionStored]
    events: List[EventTypeStored]
    observation_levels: List[ObservationLevel]

    licence: LegalReference  # for usage of data associated with this experiment
    references: List[Reference]

    start: datetime
    end: None|datetime

    cultural_practices: str
    # data: [DataReference]
    documentation: [Reference]
    contacts: List[Person]

class StudyStored(Study, Entity):
    pass

class Investigation(BaseModel):
    """
    This is like the Trial concept in BrAPI,
    But using the more widespread terminology from ISA
    https://isa-specs.readthedocs.io/en/latest/isamodel.html
    """
    name: str  #

    fullname: None | str
    description: None | str

    start: datetime
    end: None | datetime

    studies: List[StudyStored]

    program: int  # internal reference to program ID

    contacts: List[Person]

    publications: List[PublicationReference]
    references: List[Reference]

class InvestigationStored(Investigation, Entity):
    pass

class Program(BaseModel):
    name: str # e.g. Bolero
    fullname: str

    investigations: List[InvestigationStored]

    leader: Person

    funding: List[Reference]
    references: List[Reference]

    investigations: List[Investigation]

class ProgramStored(Program, Entity):
    pass
