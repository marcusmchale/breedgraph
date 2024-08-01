from pydantic import Field
from typing import List, ClassVar
from abc import ABC
from enum import Enum
from src.breedgraph.domain.model.base import StoredEntity

"""
Ontologies are designed to allow flexible annotation and description of complex meta-data
"""
#class Language(BaseModel):
#    name: str
#    code: str
#    # e.g. https://datahub.io/core/language-codes#language-codes
#    # ISO Language Codes (639-1 and 693-2) and IETF Language Types

class OntologyRelationshipLabel(str, Enum):
    RELATES_TO = 'RELATES_TO' # a generic directed relationship between entries
    HAS_CATEGORY = 'HAS_CATEGORY' # Scale -> Category
    HAS_TRAIT = 'HAS_TRAIT'  # Subject -> Trait
    HAS_CONDITION = 'HAS_CONDITION'  # Subject -> Condition
    HAS_EXPOSURE = 'HAS_EXPOSURE'  # EventEntry -> Exposure
    DESCRIBES_TRAIT = 'DESCRIBES_TRAIT' # Variable -> Trait
    DESCRIBES_CONDITION = 'DESCRIBES_CONDITION'  # Parameter -> Condition
    DESCRIBES_EXPOSURE = 'DESCRIBES_EVENT' # EventEntry -> Exposure
    USES_METHOD = 'USES_METHOD' # Variable/Parameter/EventEntry -> Method
    USES_SCALE = 'USES_SCALE' # Variable/Parameter/EventEntry -> Scale

class OntologyEntry(StoredEntity, ABC):
    label: ClassVar[str] = 'OntologyEntry'
    plural: ClassVar[str] = 'OntologyEntries'

    # Has an ID if stored, not currently using full input/output/stored model classes for ontology entries
    id: int|None = None

    name: str
    abbreviation: str|None = None
    synonyms: List[str]|None = list()

    description: str | None = None

    authors: List[int]|None = list()  # internal person ID
    references: List[int]|None = list()  # internal reference ID

    @property
    def names_lower(self):
        names = [self.name.casefold()] + [i.casefold() for i in self.synonyms]
        names = names + [self.abbreviation.casefold()] if self.abbreviation else names
        return names

class Term(OntologyEntry):  # generic ontology entry, used to relate terms to each other and traits/methods/scales
    label: ClassVar[str] = 'Term'
    plural: ClassVar[str] = 'Terms'
