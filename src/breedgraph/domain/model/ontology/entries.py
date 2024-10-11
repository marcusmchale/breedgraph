from typing import List, ClassVar
from abc import ABC
from enum import Enum
from src.breedgraph.domain.model.base import StoredModel, LabeledModel

"""
Ontologies are designed to allow flexible annotation and description of complex meta-data
"""

class ObservationMethodType(str, Enum):
    MEASUREMENT = "MEASUREMENT"
    COUNTING = "COUNTING"
    ESTIMATION = "ESTIMATION"
    COMPUTATION = "COMPUTATION"
    PREDICTION = "PREDICTION"
    DESCRIPTION = "DESCRIPTION"
    CLASSIFICATION = "CLASSIFICATION"

class ScaleType(str, Enum):
    DATE = "DATE"
    DURATION = "DURATION"
    NUMERICAL = "NUMERICAL"
    NOMINAL = "NOMINAL"  # should have categories
    ORDINAL = "ORDINAL"  # should have categories
    TEXT = "TEXT"
    GERMPLASM = "GERMPLASM"

class OntologyRelationshipLabel(str, Enum):
    RELATES_TO = 'RELATES_TO' # a generic directed relationship between entries
    # To define scale categories
    HAS_CATEGORY = 'HAS_CATEGORY' # Scale -> Category
    # To define unit subjects (see block outside ontology)
    OF_SUBJECT = 'OF_SUBJECT' # Unit -> Subject
    # To define subject traits/conditions/exposures
    #  - we prefer outgoing edges from subject in the ontology as subject has a lot of income edges from units
    HAS_TRAIT = 'HAS_TRAIT'  # Subject -> Trait
    HAS_CONDITION = 'HAS_CONDITION'  # Subject -> Condition
    HAS_EXPOSURE = 'HAS_EXPOSURE'  # Subject -> Exposure
    # Similarly, Variable/Prameter and EventType have a lot of incoming edges from StudyTerms
    # so prefer outgoing edges from these
    DESCRIBES_TRAIT = 'DESCRIBES_TRAIT' # Variable -> Trait
    DESCRIBES_CONDITION = 'DESCRIBES_CONDITION'  # Parameter -> Condition
    DESCRIBES_EXPOSURE = 'DESCRIBES_EXPOSURE' # EventType -> Exposure
    USES_METHOD = 'USES_METHOD' # Variable/Parameter/EventEntry -> Method
    USES_SCALE = 'USES_SCALE' # Variable/Parameter/EventEntry -> Scale

class OntologyBase(LabeledModel):
    label: ClassVar[str] = 'OntologyEntry'
    plural: ClassVar[str] = 'OntologyEntries'

    name: str
    abbreviation: str | None = None
    description: str | None = None
    synonyms: List[str] = list()

    authors: List[int] = list()  # internal person ID
    references: List[int] = list()  # internal reference ID

    @property
    def names(self):
        names = [self.name] + self.synonyms
        names = names + [self.abbreviation] if self.abbreviation else names
        return names

class OntologyEntry(OntologyBase, StoredModel, ABC):
    # Has a positive ID if stored, not using input/output/stored model classes for ontology entries
    id: int|None = None


class Term(OntologyEntry):  # generic ontology entry, used to relate terms to each other and traits/methods/scales
    label: ClassVar[str] = 'Term'
    plural: ClassVar[str] = 'Terms'
