from src.breedgraph.adapters.repositories.base import Entity

from src.breedgraph.domain.model.ontologies.entries import OntologyEntry



class LocationType(OntologyEntry):
    """
    e.g. country, region, state, city, etc.
    """
    pass

class LocationTypeStored(LocationType, Entity):
    pass
