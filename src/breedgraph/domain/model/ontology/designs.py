from dataclasses import dataclass, field
from breedgraph.domain.model.ontology.entries import OntologyEntryBase, OntologyEntryInput, OntologyEntryStored
from breedgraph.domain.model.ontology.enums import OntologyEntryLabel
from typing import ClassVar, List

@dataclass
class DesignBase(OntologyEntryBase):
    """
    To describe types of experimental design
    """
    label: ClassVar[OntologyEntryLabel] = OntologyEntryLabel.DESIGN

@dataclass
class DesignInput(DesignBase, OntologyEntryInput):
    pass

@dataclass
class DesignStored(DesignBase, OntologyEntryStored):
    pass
