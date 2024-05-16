from pydantic import BaseModel, Field

from typing import List

from src.breedgraph.domain.model.references import Reference
from src.breedgraph.adapters.repositories.base import Entity

"""
Ontologies are designed to allow flexible annotation and description of complex meta-data
"""

class Language(BaseModel):
    name: str
    code: str
    # e.g. https://datahub.io/core/language-codes#language-codes
    # ISO Language Codes (639-1 and 693-2) and IETF Language Types

class Version(BaseModel):
    major: int
    minor: int
    patch: int
    comment: str

    @property
    def name(self) -> str:
        return f"{self.major}.{self.minor}.{self.patch}-{self.comment}"

class VersionStored(Version, Entity):
    """
        Ontology version is associated with it's respective entries.
        When a new term is added, this means a new version, but may be a minor/patch version
        Major version changes should reflect a curated commit.

        todo
          consider edits that may not require creation of a new entry
          e.g. addition of references/synonyms.
    """
    pass

class OntologyEntry(BaseModel):
    name: str
    abbreviation: str|None = None
    synonyms: List[str] = list()

    description: str|None = None

    authors: List[int] = list()  # internal person ID
    references: List[int] = list()  # internal reference ID

    parents: List[int] = Field(frozen=True, default=list())
    children: List[int] = Field(frozen=True, default=list())

class OntologyEntryStored(OntologyEntry, Entity):
    pass

class Term(OntologyEntry):  # generic ontology entry, used to relate terms to each other and traits/methods/scales
    pass

class TermStored(Term, Entity):
    pass
