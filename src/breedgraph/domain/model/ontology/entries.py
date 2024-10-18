from typing import List, ClassVar
from abc import ABC
from src.breedgraph.domain.model.base import StoredModel, LabeledModel

"""
Ontologies are designed to allow flexible annotation and description of complex meta-data
"""

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
