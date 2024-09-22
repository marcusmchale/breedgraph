from enum import Enum

from src.breedgraph.domain.model.base import LabeledModel
from src.breedgraph.domain.model.time_descriptors import PyDT64
from src.breedgraph.domain.model.controls import ControlledModel, ControlledRootedAggregate
from src.breedgraph.domain.model.ontology.entries import OntologyBase

from typing import List, Dict, ClassVar, Type

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
    Further details may be described by a GermplasmMethod in the ontology
    """
    CLONAL = 'CLONAL'  # e.g maintenance in tissue culture
    SEXUAL = 'SEXUAL'  # e.g. self-pollination
    APOMIXIS = 'APOMIXIS' # e.g. clonal seed production

class GermplasmEntry(OntologyBase):
    # For germplasm entries we subclass ontology base
    # so we can return them as categories for a scale.

    label: ClassVar[str] = 'Germplasm'
    plural: ClassVar[str] = 'Germplasms'

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

    Methods should be references to GermplasmMethods in the Ontology that define protocols, e.g.
      - crossing
      - clonal propagation via tissue culture
      - controlled self-fertilisation
      - uncontrolled pollination
    """
    origin: int | None = None
    time: PyDT64 | None = None
    reproduction: Reproduction | None = None
    methods: List[int] = list()

    def __hash__(self):
        return hash(self.name)

class GermplasmEntryInput(GermplasmEntry):
    pass

class GermplasmEntryStored(GermplasmEntry, ControlledModel):

    def redacted(self):
        return self.model_copy(deep=True, update={
            'name': self.redacted_str,
            'synonyms': [self.redacted_str for _ in self.synonyms],
            'description': self.redacted_str if self.description is not None else self.description,
            'reproduction': None,
            'origin': None,
            'time': None,
            'methods': list(),
            'references': list()
        })

class Germplasm(ControlledRootedAggregate):
    default_edge_label: ClassVar[str] = GermplasmSourceType.UNKNOWN
    default_model_class: ClassVar[Type[ControlledModel]] = GermplasmEntryStored
    """
    A Germplasm aggregate is a collection of related germplasm entries,
    typically rooted at a single Crop reference, e.g. coffee or cocoa.
    The Germplasm aggregate manages Sourcing and Maintenance details for the entries within it.
    These details contain references to Ontology entries for Methods, and Region entries for Locations.

    e.g. Coffee <- Coffea arabica <- Marsellesa <- Centroamericano -> MSH12 ...

    From the relationships we can infer some key labels,
    e.g.
      - is an Accession where location and time are provided.
      - is a hybrid where maternal and paternal are known and distinct.
      - is a controlled self-fertilisation where maternal and paternal are known and the same
      - is clonal tissue where source is singular Tissue relationship.
    """
    def add_entry(self, entry: GermplasmEntry, sources: Dict[int, dict|None] = None) -> int:
        if sources is not None:
            for key in sources:
                if sources[key] is None:
                    sources[key] = {'type': self.default_edge_label}
                if not 'type' in sources[key]:
                    sources[key]['type'] = self.default_edge_label

        return super().add_entry(entry, sources if sources is not None else None)


    def insert_root(self, entry: LabeledModel, details: dict = None) -> int:
        if details is None:
            details = {}
        if 'type' not in details or details['type'] is None:
            details = {'type': self.default_edge_label}
        return super().insert_root(entry, details)

