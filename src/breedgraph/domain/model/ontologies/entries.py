from pydantic import Field, root_validator

from typing import List

from src.breedgraph.adapters.repositories.base import Entity

"""
Ontologies are designed to allow flexible annotation and description of complex meta-data
"""

#class Language(BaseModel):
#    name: str
#    code: str
#    # e.g. https://datahub.io/core/language-codes#language-codes
#    # ISO Language Codes (639-1 and 693-2) and IETF Language Types

class OntologyEntry(Entity):
    """
    ID of 0 is a placeholder to be used when constructing a new entry.
    This value is replaced with a negative value to use as the key in the repo before commit to DB.
    This value is then replaced with a positive value when it is stored by the repository into DB.
    """
    id: int = 0

    name: str
    description: str | None = None

    abbreviation: str|None = None
    synonyms: List[str]|None = list()

    authors: List[int]|None = list()  # internal person ID
    references: List[int]|None = list()  # internal reference ID

    parents: List[int]|None = Field(frozen=True, default=list())
    children: List[int]|None = list()

class Term(OntologyEntry):  # generic ontology entry, used to relate terms to each other and traits/methods/scales
    pass
