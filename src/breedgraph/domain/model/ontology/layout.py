from src.breedgraph.domain.model.ontology.entries import OntologyEntry
from typing import ClassVar

class Layout(OntologyEntry):
    label: ClassVar[str] = 'Layout'
    plural: ClassVar[str] = 'Layouts'
    """
    e.g. rows, grid, measured distance
    Must define interpretation for x, y, and z parameters

    Layouts may be applied to unit positions within a location
    """
    pass
