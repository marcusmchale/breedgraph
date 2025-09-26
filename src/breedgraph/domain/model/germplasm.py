import re
from enum import Enum
from abc import ABC
from dataclasses import dataclass, field, replace
from numpy import datetime64

from src.breedgraph.service_layer.tracking.wrappers import asdict
from src.breedgraph.domain.model.base import LabeledModel
from src.breedgraph.domain.model.organisations import Access
from src.breedgraph.domain.model.controls import ControlledModel, Controller

from typing import List, ClassVar, Self, Dict, Any

class GermplasmSourceType(str, Enum):
    # This is to broadly classify relationships, further details may be described in the method,
    # and specific details in the germplasm sourcing description
    UNKNOWN = 'UNKNOWN'  # Germplasm is derived from source, though details of the relationship are not known.
    SEED = 'SEED'  # Germplasm is derived from seed obtained from source.
    TISSUE = 'TISSUE'  # Germplasm is derived from vegetative tissue from source.
    MATERNAL = 'MATERNAL'  # Germplasm is derived from seed obtained from source in a controlled cross.
    PATERNAL = 'PATERNAL'  # Germplasm is derived from pollen obtained from source in a controlled cross.

class Reproduction(str, Enum):
    """
    Class of reproduction used to maintain this germplasm
    Further details may be described by a ControlMethod in the ontology
    """
    CLONAL = 'CLONAL'  # e.g maintenance in tissue culture
    SEXUAL = 'SEXUAL'  # e.g. self-pollination
    APOMIXIS = 'APOMIXIS' # e.g. clonal seed production

@dataclass
class GermplasmRelationship:
    source_id: int
    target_id: int
    source_type: GermplasmSourceType = GermplasmSourceType.UNKNOWN
    description: str | None = None

    def model_dump(self) -> Dict[str, Any]:
        dump = asdict(self)
        dump['source_type'] = dump['source_type'].value
        return dump

    def __post_init__(self):
        self.source_type = GermplasmSourceType(self.source_type)

@dataclass
class GermplasmBase(ABC):
    # For germplasm entries we subclass ontology base
    # so we can return them as categories for a scale.
    label: ClassVar[str] = 'Germplasm'
    plural: ClassVar[str] = 'Germplasms'
    protected_characters: ClassVar[List[str]] = ['/', '*', ';']

    name: str = ''
    description: str | None = None
    synonyms: List[str] = field(default_factory=list)

    authors: List[int] = field(default_factory=list)  # internal person ID
    references: List[int] = field(default_factory=list)  # internal reference ID

    origin: int | None = None
    time: datetime64 | None = None

    reproduction: Reproduction | None = None
    control_methods: List[int] = field(default_factory=list)
    """
    Germplasm entries may include:
        crop, e.g. Coffee, Cocoa
        species, e.g. arabica, robusta etc.
        cultivars, e.g. Caturra, Geisha
        landraces, e.g. YirgaChefe
            - note we are not storing location information specifically in the ontology
              but this detail can be added in the description or references
        hybrids, e.g. Centramericano (H1)
        etc.
        
    Origin should be a reference to a Location in Regions
        where this Germplasm was sourced or created.
        
    Time should be the time of sourcing/creation at origin.

    Methods should be references to ControlMethods in the Ontology that define protocols, e.g.
      - crossing
      - clonal propagation via tissue culture
      - controlled self-fertilisation
      - uncontrolled pollination
      
    When used as categories in a scale, special characters may be used for values:
      - '/' describes a graft, starting from the scion tissue down to rootstock material, i.e. scion/intergraft/rootstock
      - '*' describes F1 material from a cross between the described germplasms.
        - Multiple F1 materials described in this way are assumed to be from independent events.
        - To describe repeated use of a single hybridization event, e.g. clonal F1 material, an entry should be created.
      - ';' is used to separate a list of germplasm entries, i.e. when multiple germplasm values are being reported as the value.

    The "protected" characters may not be used in names. 
    Similarly, a name may not be a simple integer alone. 
    This is to avoid confounding entries when describing such.
    """
    @property
    def names(self):
        names = [self.name] + self.synonyms
        return names

    def __post_init__(self):
        """Validate that name doesn't contain protected characters or is numeric"""
        if re.search('|'.join(re.escape(x) for x in self.protected_characters), self.name):
            raise ValueError(f"Name {self.name} contains a protected character {self.protected_characters}")

        try:
            float(self.name)
        except ValueError:
            pass
        else:
            raise ValueError("Names for germplasm entries cannot be purely numeric")

    def model_dump(self) -> Dict[str, Any]:
        dump = asdict(self)
        return dump

@dataclass
class GermplasmInput(GermplasmBase, LabeledModel):
    pass

@dataclass
class GermplasmStored(GermplasmBase, ControlledModel):

    def redacted(
            self,
            controller: Controller,
            user_id=None,
            read_teams=None
    ) -> Self:
        if controller.has_access(Access.READ, user_id, read_teams):
            return self
        else:
            return replace(
                self,
                name = self.redacted_str,
                synonyms = [self.redacted_str for _ in self.synonyms],
                description = self.description and self.redacted_str,
                reproduction = None,
                origin = None,
                time = None,
                control_methods = list(),
                references = list()
            )

@dataclass
class GermplasmOutput(GermplasmBase, LabeledModel):
    pass

