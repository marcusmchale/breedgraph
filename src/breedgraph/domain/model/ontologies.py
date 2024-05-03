
from enum import Enum
from pydantic import BaseModel

from src.breedgraph.domain.model.people import Person
from src.breedgraph.domain.model.references import Reference
from typing import List


class Crop(BaseModel):
    name: str

class CropStored(Crop):
    id: int

class Version(BaseModel):
    major: int
    minor: int
    patch: int
    comment: str

    @property
    def name(self) -> str:
        return f"{self.major}.{self.minor}.{self.patch}-{self.comment}"

class Ontology(BaseModel):
    name: str
#    description: str
#    documentation: Reference
#
#    version: Version
#    authors: List[Person]
#
#    copyright: Reference
#    licence: Reference
#
#    references: [Reference]
#
#    parent: int = None
#    children: List[int]
#
#class OntologyStored(Ontology):
#    id: int