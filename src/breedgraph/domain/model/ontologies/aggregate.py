from pydantic import BaseModel, computed_field

from src.breedgraph.adapters.repositories.base import Aggregate, AggregateRoot
from src.breedgraph.domain.model.references import Reference
from src.breedgraph.domain.model.ontologies.entries import OntologyEntry, OntologyEntryStored

from typing import List

class Version(BaseModel):
    major: int
    minor: int
    patch: int
    comment: str

    @property
    def name(self) -> str:
        return f"{self.major}.{self.minor}.{self.patch}-{self.comment}"


class Ontology(Aggregate): 
    references: List[OntologyEntry]
    version: Version = Version(major=1, minor=0, patch=0, comment="Initial version")

    copyright: Reference|None = None
    licence: Reference|None = None

    def get_reference(self, reference: int):
        for r in self.references:
            if isinstance(r, OntologyEntryStored) and r.id == reference:
                return r
    @computed_field
    @property
    def root(self) -> AggregateRoot | OntologyEntry:
        return self.references[0]

    @property
    def protected(self) -> str | bool:
        protected_message = "This ontology is in use and cannot be removed"
        def is_used(reference: OntologyEntry):
            if isinstance(reference, OntologyEntryStored):
                if reference.used:
                    return True
                for child_ref in reference.children:
                    child_used = is_used(self.get_reference(child_ref))
                    if child_used:
                        return child_used

        if is_used(self.root):
            return protected_message

    def __hash__(self):
        return hash(self.root.id)
