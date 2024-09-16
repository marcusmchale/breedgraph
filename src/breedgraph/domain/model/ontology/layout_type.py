from src.breedgraph.domain.model.ontology.entries import OntologyEntry
from typing import ClassVar

class LayoutType(OntologyEntry):
    label: ClassVar[str] = 'LayoutType'
    plural: ClassVar[str] = 'LayoutTypes'
    """
    e.g. rows, grid, measured distance
    Must define interpretation for x, y, and z parameters

    Layouts may be applied to unit positions within a location
    """
    pass
