from dataclasses import dataclass, field
from src.breedgraph.domain.model.ontology.entries import (
    OntologyEntryBase, OntologyEntryInput, OntologyEntryStored, OntologyEntryOutput
)
from src.breedgraph.domain.model.ontology.enums import OntologyEntryLabel

from typing import ClassVar

@dataclass
class LocationTypeBase(OntologyEntryBase):
    label: ClassVar[OntologyEntryLabel] = OntologyEntryLabel.LOCATION_TYPE
    """
    e.g. country, region, state, city, etc.
    """

@dataclass
class LocationTypeInput(LocationTypeBase, OntologyEntryInput):
    pass

@dataclass
class LocationTypeStored(LocationTypeBase, OntologyEntryStored):
    pass

@dataclass
class LocationTypeOutput(LocationTypeBase, OntologyEntryOutput):
    terms: list[int] = field(default_factory=list)

