import logging

from enum import Enum, IntEnum
from pydantic import BaseModel, Field, field_validator
from datetime import datetime

from src.breedgraph.domain.model.ontologies import Crop
from src.breedgraph.domain.model.enums import ScientificType
from src.breedgraph.domain.model.people import Person
from src.breedgraph.domain.model.references import (
    Reference,
    IdentifiedReference,
    PublicationReference,
    DataReference,
    LegalReference
)
from src.breedgraph.domain.model.environment import EnvironmentParameter
from src.breedgraph.domain.events.accounts import Event

from typing import List

logger = logging.getLogger(__name__)

class Study(BaseModel):
    name: str
    fullname: None|str
    external_id: str  # an permanent external identifier, e.g. DOI
    description: str
    crop: Crop

    start: datetime
    end: None|datetime

    cultural_practices: str
    data: [DataReference]
    documentation: [Reference]
    contacts: List[Person]

    environment_parameters: List[EnvironmentParameter]
    observation_levels: List[ObservationLevel]

class Trial(BaseModel):
    name: str
    crop: Crop

    fullname: None | str
    description: None | str

    start: datetime
    end: None | datetime

    program: int  # internal reference to program ID

    contacts: List[Person]

    publications: List[PublicationReference]
    references: List[Reference]

class TrialStored(Trial):
    id: int

class Program(BaseModel):
    name: str
    fullname: str

    crop: Crop
    leader: Person

    funding: List[Reference]
    references: List[Reference]

    trials: List[Trial]

class ProgramStored(Program):
    id: int
