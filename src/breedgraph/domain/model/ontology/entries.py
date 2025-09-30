from typing import List, ClassVar, Any, Dict
from abc import ABC, abstractmethod
from dataclasses import dataclass, field

from src.breedgraph.service_layer.tracking.wrappers import asdict
from src.breedgraph.domain.model.base import LabeledModel, StoredModel, EnumLabeledModel
from src.breedgraph.domain.model.ontology.enums import OntologyEntryLabel

"""
Ontologies are designed to allow flexible annotation and description of complex meta-data
They form a knowledge graph with Entries and Relationships between them

Ontology entry with ID of 0 should be handled in presentation layer as undefined for redacted results. 
"""

@dataclass
class OntologyEntryBase(EnumLabeledModel, ABC):
    """
    Common domain fields for all ontology entries.
    Concrete entry families (e.g., DesignBase, TraitBase) should inherit this.
    """
    label: ClassVar[OntologyEntryLabel]
    name: str = ''  # unique lowercase per label
    abbreviation: str | None = None # if provided, must be unique in lowercase (for a given label)
    description: str | None = None
    synonyms: List[str] = field(default_factory=list)  # these don't have to be unique
    authors: List[int] = field(default_factory=list)  # internal person ID
    references: List[int] = field(default_factory=list)  # internal reference ID

    @property
    def names(self):
        """Convenience accessor including synonyms and optional abbreviation."""
        names = [self.name] + self.synonyms
        names = names + [self.abbreviation] if self.abbreviation else names
        return names

    @property
    def abbreviation_lower(self) -> str:
        return self.abbreviation.casefold() if self.abbreviation else None

    def model_dump(self) -> Dict[str, Any]:
        dump = asdict(self)
        if 'scale_type' in dump:
            dump['scale_type'] = dump['scale_type'].value
        if 'observation_type' in dump:
            dump['observation_type'] = dump['observation_type'].value
        if 'axes' in dump:
            dump['axes'] = [a.value for a in dump['axes']]
        return dump

@dataclass
class OntologyEntryInput(OntologyEntryBase, ABC):
    """
    Combine with a concrete *Base class, e.g.:
      class DesignInput(DesignBase, OntologyEntryInput): ...
    """
    pass

@dataclass
class OntologyEntryStored(OntologyEntryBase, StoredModel, ABC):
    """
    Combine with a concrete *Base class, e.g.:
      class DesignStored(DesignBase, OntologyEntryStored): ...
    """
    pass

@dataclass
class OntologyEntryOutput(OntologyEntryBase, ABC):
    """
    Combine with a concrete *Base class, e.g.:
      class DesignOutput(DesignBase, OntologyEntryOutput): ...
    """
    id: int = None
    parents: List[int] = field(default_factory=list)
    children: List[int] = field(default_factory=list)

@dataclass
class TermBase(OntologyEntryBase):
    """
    Generic ontology entry used primarily as a bridge/target for relationships.
    Terms serve as the primary sink for RELATES_TO relationships and can
    relate to other entities or other Terms.
    """
    label: ClassVar[str] = OntologyEntryLabel.TERM

@dataclass
class TermInput(TermBase, OntologyEntryInput):
    pass

@dataclass
class TermStored(TermBase, OntologyEntryStored):
    related_to: List[int] = field(default_factory=list)  # the incoming entry ids from any other entry type

@dataclass
class TermOutput(TermBase, OntologyEntryOutput):
    subjects: List[int] = field(default_factory=list)
    scales: List[int] = field(default_factory=list)
    categories: List[int] = field(default_factory=list)
    observation_methods: List[int] = field(default_factory=list)
    traits: List[int] = field(default_factory=list)
    variables: List[int] = field(default_factory=list)
    control_methods: List[int] = field(default_factory=list)
    conditions: List[int] = field(default_factory=list)
    factors: List[int] = field(default_factory=list)
    events: List[int] = field(default_factory=list)
    location_types: List[int] = field(default_factory=list)
    layout_types: List[int] = field(default_factory=list)
    designs: List[int] = field(default_factory=list)
    roles: List[int] = field(default_factory=list)
    titles: List[int] = field(default_factory=list)
