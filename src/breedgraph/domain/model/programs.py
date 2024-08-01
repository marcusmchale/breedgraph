import logging

from enum import Enum, IntEnum
from pydantic import BaseModel, Field, field_validator
from time_descriptors import TimeDescriptor
from datetime import datetime

from src.breedgraph.domain.model.ontology import (
    Condition,
    Subject,
    Design,
    EventEntry, Variable, Parameter
)
from src.breedgraph.domain.model.germplasm import GermplasmEntryStored
from src.breedgraph.domain.model.people import PersonBase
from src.breedgraph.domain.model.regions import LocationStored
from src.breedgraph.domain.model.references import (
    Reference,
    IdentifiedReference,
    PublicationReference,
    DataReference,
    LegalReference
)

from src.breedgraph.domain.model.base import StoredEntity, Aggregate

from typing import List, Set

logger = logging.getLogger(__name__)

class FactorLevel(BaseModel):
    """
    MIAPPE DM60: exposure or condition that is being tested.

    Factor should be a reference to Event or Parameter in the ontology.
    Level should define a value for this that is being assessed

    Factors may vary beyond typical exposures or conditions,
    E.g. In Bolero, we might consider Germplasm as a factor
     in this case "Genotype" may be defined as a condition,
     with the levels then corresponding to germplasm references
    """
    factor: int
    level: str|int|float

class Study(BaseModel):
    """
    This is like the Study concept
    https://isa-specs.readthedocs.io/en/latest/isamodel.html
    """
    name: str

    fullname: str|None = None
    description: str|None = None
    external_id: str|None = None # a permanent external identifier, e.g. DOI

    variables: List[int]
    parameters: List[int]
    events: List[int]

    # Each entry in outside set is a unique set of FactorLevels
    # All sets of factor levels is defined by experimental unit ~ factor_level
    factors: Set[Set[FactorLevel]]

    germplasm: List[int]
    location: int
    design: int

    units: List[int]

    licence: int  # for usage of data associated with this experiment
    references: List[int]

    start: TimeDescriptor
    end: None|TimeDescriptor

    cultural_practices: str
    # data: [DataReference]
    documentation: [Reference]
    contacts: List[PersonBase]


class StudyStored(Study, StoredEntity):
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

    contacts: List[PersonBase]

    publications: List[PublicationReference]
    references: List[Reference]

class InvestigationStored(Investigation, StoredEntity):
    pass

class Program(BaseModel):
    name: str # e.g. Bolero
    fullname: str

    investigations: List[InvestigationStored]

    leader: PersonBase

    funding: List[Reference]
    references: List[Reference]

    investigations: List[Investigation]

class ProgramStored(Program, StoredEntity):
    pass
