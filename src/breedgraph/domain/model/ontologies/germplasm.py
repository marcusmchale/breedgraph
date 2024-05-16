from pydantic import BaseModel

from src.breedgraph.domain.model.ontologies.entries import OntologyEntry
from src.breedgraph.domain.model.time_descriptors import TimeDescriptor

from src.breedgraph.adapters.repositories.base import Entity

class Maintenance(OntologyEntry):
    """
        Germplasm maintenance process, e.g. Seed, Clonal
    """
    pass

class MaintenanceStored(Maintenance, Entity):
    pass

class Sourcing(OntologyEntry):
    """
        Germplasm sourcing:
         - e.g. collection, mutagenesis, controlled crossing (probably many types for coffee)
    """
    pass

class SourcingStored(Sourcing, Entity):
    pass


class Attribute(OntologyEntry):
    """
        Germplasm attribute:
         - e.g. Heat tolerant etc, QTL, etc.
    """

class AttributeStored(Attribute, Entity):
    pass