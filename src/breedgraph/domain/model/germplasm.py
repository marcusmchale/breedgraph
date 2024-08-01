import copy
import networkx as nx

from pydantic import BaseModel, computed_field
from enum import Enum
from src.breedgraph.domain.model.organisations import Access
from src.breedgraph.domain.model.base import LabeledModel, StoredEntity, RootedAggregate
from src.breedgraph.domain.model.time_descriptors import TimeDescriptor
from src.breedgraph.domain.model.controls import ControlledModel, ControlledAggregate, ReadRelease

from typing import List, Dict, Tuple, ClassVar, Set

class GermplasmSourceType(str, Enum):
    # This is to broadly classify relationships, further details may be described in the method,
    # and specific details in the source relationship description
    UNKNOWN = 'UNKNOWN'  # Germplasm is derived from source, though details of the relationship are not known.

    SEED = 'SEED'  # Germplasm is derived from seed obtained from source.
    MATERNAL = 'MATERNAL'  # Germplasm is derived from seed obtained from source in a controlled cross.
    PATERNAL = 'PATERNAL'  # Germplasm is derived from pollen obtained from source in a controlled cross.

    TISSUE = 'TISSUE'  # Germplasm is derived from tissue from source.
    SCION = 'SCION'  # Germplasm apical tissues are derived from source.
    ROOTSTOCK = 'ROOTSTOCK' # Germplasm root tissues are derived from source.
    INTERGRAFT = 'INTERGRAFT' # Germplasm stem tissues (between apical and root) are derived from source.

class Reproduction(str, Enum):
    """
    Class of reproduction used to maintain this germplasm
    Further details may be described by a GermplasmMethod in the ontology
    """
    CLONAL = 'CLONAL'  # e.g maintenance in tissue culture
    SEXUAL = 'SEXUAL'  # e.g. self-pollination

class GermplasmEntry(LabeledModel):
    label: ClassVar[str] = 'GermplasmEntry'
    plural: ClassVar[str] = 'GermplasmEntries'

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
        
    Reproduction may be None if the germplasm is not maintained due to reproductive constraints,
        e.g. F1 hybrid that is not fertile 
    OR where it is not maintained by choice,
        e.g. an F1 hybrid may not be maintained because there is no interest in the recombinant F2 population.
    No distinction is made here, as in many cases it is

    Maintenance should be a reference to a GermplasmMethod in the Ontology that defines e.g.
      - clonal propagation via tissue culture,
      - controlled self-fertilisation,
      - uncontrolled pollination
      - clonal apomictic reproduction
    """
    name: str
    synonyms: List[str] = list()
    description: str | None = None
    reproduction: Reproduction | None = None
    maintenance: int | None = None
    references: List[int] = list()  # internal reference ID

    @property
    def names(self):
        return [self.name] + self.synonyms

class GermplasmEntryInput(GermplasmEntry, ControlledModel):
    pass

class GermplasmEntryStored(GermplasmEntry, ControlledModel, StoredEntity):
    pass

class SourceDetails(BaseModel):
    """
    These details define the relationship between a source and sink GermplasmEntry.
    Type is required and provides basic details of the relationship.

    Sourcing should be a reference to a GermplasmMethod in the Ontology
        that is specific to sourcing this germplasm, e.g. a protocol for crossing
    Location should be a reference to a Location in Regions
        where this source relationship was obtained/performed
    Time may be one of many TimeDescriptors for the source time
    Description can outline additional details.
    References are to link internal stored references.
    """
    label: GermplasmSourceType
    sourcing: int | None = None
    location: int | None = None
    time: TimeDescriptor | None = None
    description: str = None
    references: List[int] = list()  # internal reference ID

class Germplasm(ControlledAggregate, RootedAggregate):
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
      - is a graft where scion/intergraft or rootstock are known
      - is clonal tissue where source is singular Tissue relationship.
    """

    def set_attribute(self, germplasm_id, trait_id, value):
        """
            Attributes are to describe heritable trait values for a germplasm entry.
            TODO finalise this when we have finalised the recording of variables/parameters/events etc.
        """
        raise NotImplementedError

    def get_attributes(self, germplasm_id, trait_id = None) -> Dict[str, int|float|str]:
        raise NotImplementedError
            # return all traits

    def redacted(self, read_teams: Set[int] = None) -> 'Germplasm':
        if read_teams is None:
            read_teams = set()

        g = copy.deepcopy(self.graph)
        def remove_node_and_reconnect(n):
            for in_src, _ in g.in_edges(n):
                for _, out_dst in g.out_edges(n):
                    g.add_edge(in_src, out_dst, label=GermplasmSourceType.UNKNOWN)
            g.remove_node(n)

        root_id = self.get_root_id()
        for node_id in list(g.nodes):
            entry = g.nodes[node_id]['model']
            if not entry.controller.has_access(Access.READ, read_teams):
                if node_id == root_id:
                    entry.name = self._redacted_str
                    entry.synonyms = [self._redacted_str for i in entry.synonyms]
                    entry.description = None if entry.description is None else self._redacted_str
                    entry.reproduction = None
                    entry.maintenance = None
                    entry.references = list()
                else:
                    remove_node_and_reconnect(node_id)

        germplasm = Germplasm()
        germplasm.graph = g
        return germplasm