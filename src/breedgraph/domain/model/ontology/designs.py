from dataclasses import dataclass, field
from src.breedgraph.domain.model.ontology.entries import OntologyEntryBase, OntologyEntryInput, OntologyEntryStored, OntologyEntryOutput
from src.breedgraph.domain.model.ontology.enums import OntologyEntryLabel
from typing import ClassVar, List

@dataclass
class DesignBase(OntologyEntryBase):
    """
    To describe types of experimental design
    """
    label: ClassVar[str] = OntologyEntryLabel.DESIGN

@dataclass
class DesignInput(DesignBase, OntologyEntryInput):
    pass

@dataclass
class DesignStored(DesignBase, OntologyEntryStored):
    pass

@dataclass
class DesignOutput(DesignBase, OntologyEntryOutput):
    terms: List[int] = field(default_factory=list)