from src.breedgraph.adapters.repositories.base import Entity

from src.breedgraph.domain.model.ontologies.entries import OntologyEntry



class FacilityType(OntologyEntry):
    """
    e.g. research field, institute, glasshouse, chamber etc.
    """
    pass

class FacilityTypeStored(FacilityType, Entity):
    pass
