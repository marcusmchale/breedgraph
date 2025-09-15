"""
Germplasm method ontology entries for germplasm management and breeding techniques.
Defines methods used in germplasm collection, maintenance, and breeding operations.
"""
from dataclasses import dataclass, field
from src.breedgraph.domain.model.ontology.entries import (
    OntologyEntryBase, OntologyEntryInput, OntologyEntryStored, OntologyEntryOutput
)
from typing import List, ClassVar

@dataclass
class GermplasmMethodBase(OntologyEntryBase):
    label: ClassVar[str] = 'GermplasmMethod'
    plural: ClassVar[str] = 'GermplasmMethods'

@dataclass
class GermplasmMethodInput(GermplasmMethodBase, OntologyEntryInput):
    pass

@dataclass
class GermplasmMethodStored(GermplasmMethodBase, OntologyEntryStored):
    pass

@dataclass
class GermplasmMethodOutput(GermplasmMethodBase, OntologyEntryOutput):
    terms: List[int] = field(default_factory=list)
