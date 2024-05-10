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


class OntologyEntry(BaseModel):
    name: str
    abbreviation: str
    synonyms: List[str] = list()

    description: str|None = None

    language: Language = Language(name='English', code='eng')

    authors: List[int] = list()  # internal person ID
    references: List[int] = list()  # internal reference ID

    parents: List[int] = list() # ontology entry IDs, to be stored with related_to towards parent
    children: List[int] = list() # ontology entry IDs, to be stored with related_to towards self

    used: bool = False  # Whether the ontology entry is directly referenced outside the ontology

class Term(OntologyEntry):  # generic ontology entry, used to relate terms to each other and traits/methods/scales
    pass

class TermStored(Term, Entity):
    pass
