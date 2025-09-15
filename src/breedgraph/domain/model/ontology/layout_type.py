from dataclasses import dataclass, field
from src.breedgraph.domain.model.ontology.entries import (
    OntologyEntryBase, OntologyEntryInput, OntologyEntryStored, OntologyEntryOutput
)
from src.breedgraph.domain.model.ontology.enums import AxisType

from typing import ClassVar, List

@dataclass
class LayoutTypeBase(OntologyEntryBase):
    label: ClassVar[str] = 'LayoutType'
    plural: ClassVar[str] = 'LayoutTypes'
    """
    e.g. rows, grid, measured distance
    Each axis type should be defined here and match all instances of this Layout,
     though the order may be different in Layout instances
    """
    axes: List[AxisType] = field(default_factory=list)

@dataclass
class LayoutTypeInput(LayoutTypeBase, OntologyEntryInput):
    pass

@dataclass
class LayoutTypeStored(LayoutTypeBase, OntologyEntryStored):
    pass

@dataclass
class LayoutTypeOutput(LayoutTypeBase, OntologyEntryOutput):
    terms: List[int] = field(default_factory=list)
