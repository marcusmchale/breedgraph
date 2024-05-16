"""

To describe types of experimental design, these are referened in the descriptions of

"""
from src.breedgraph.domain.model.ontologies.entries import OntologyEntry
from src.breedgraph.adapters.repositories.base import Entity


class Design(OntologyEntry):
    pass

class DesignStored(OntologyEntry, Entity):
    pass
