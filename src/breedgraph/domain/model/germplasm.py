import re
from enum import Enum

from pydantic import model_validator

from src.breedgraph.domain.model.base import LabeledModel
from src.breedgraph.domain.model.organisations import Access
from src.breedgraph.domain.model.time_descriptors import PyDT64
from src.breedgraph.domain.model.controls import ControlledModel, ControlledRootedAggregate, Controller
from src.breedgraph.domain.model.ontology.entries import OntologyBase

from typing import List, Dict, ClassVar, Type, Self, Generator

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
    protected_characters: ClassVar[List[str]] = ['/', '*', ';']
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
      
    When used as categories in a scale, special characters may be used for values:
      - '/' describes a graft, starting from the scion tissue down to rootstock material, i.e. scion/intergraft/rootstock
      - '*' describes F1 material from a cross between the described germplasms.
        - Multiple F1 materials described in this way are assumed to be from independent events.
        - To describe repeated use of a single hybridization event, e.g. clonal F1 material, an entry should be created.
      - ';' is used to separate a list of germplasm entries, i.e. when multiple germplasm values are being reported as the value.
    
    As names are only guaranteed unique within a given "germplasm", 
    we translate inputs for these to germplasm ID for records.   
    The "protected" characters may not be used in names. 
    Similarly, a name may not be a simple integer alone. 
    This is to avoid confounding entries when describing such.

    """
    origin: int | None = None
    time: PyDT64 | None = None
    reproduction: Reproduction | None = None
    methods: List[int] = list()

    @model_validator(mode='after')
    def validate_names(self) -> Self:
        for name in self.names:
            if re.search('|'.join(re.escape(x) for x in self.protected_characters), name):
                raise ValueError(f"Name {name} contains a protected character {self.protected_characters}")
            try:
                int(name)
            except ValueError:
                pass
            else:
                raise ValueError("Names for germplasm entries cannot be integers")

        return self

class GermplasmEntryInput(GermplasmEntry):
    pass

class GermplasmEntryStored(GermplasmEntry, ControlledModel):

    def redacted(
            self,
            controller: Controller,
            user_id=None,
            read_teams=None
    ):
        if controller.has_access(Access.READ, user_id, read_teams):
            return self
        else:
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
    def yield_entry_id_by_name(self, name: str) -> Generator[int, None, None]:
        for entry_id, entry in self.entries.items():
            if name.casefold() in [n.casefold() for n in entry.names]:
                yield entry_id

    def assure_name_is_unique(self, name):
        try:
            next(self.yield_entry_id_by_name(name))
        except StopIteration:
            pass
        else:
            raise ValueError(f"Name is already in use for this germplasm: {name}")

    def add_entry(self, entry: GermplasmEntry, sources: Dict[int, dict|None] = None) -> int:
        if sources is not None:
            for key in sources:
                if sources[key] is None:
                    sources[key] = {'type': self.default_edge_label}
                if not 'type' in sources[key]:
                    sources[key]['type'] = self.default_edge_label

        for name in entry.names:
            self.assure_name_is_unique(name)

        return super().add_entry(entry, sources if sources is not None else None)

    def insert_root(self, entry: GermplasmEntry, details: dict = None) -> int:
        if details is None:
            details = {}
        if 'type' not in details or details['type'] is None:
            details = {'type': self.default_edge_label}

        for name in entry.names:
            self.assure_name_is_unique(name)

        return super().insert_root(entry, details)
