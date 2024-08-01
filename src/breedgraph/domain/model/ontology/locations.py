from src.breedgraph.domain.model.ontology.entries import OntologyEntry
from typing import ClassVar

class Location(OntologyEntry):
    label: ClassVar[str] = 'LocationType'
    plural: ClassVar[str] = 'LocationTypes'
    """
    e.g. country, region, state, city, etc.
    """
    pass
