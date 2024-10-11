from src.breedgraph.domain.model.ontology.entries import OntologyEntry
from typing import ClassVar

class LayoutType(OntologyEntry):
    label: ClassVar[str] = 'LayoutType'
    plural: ClassVar[str] = 'LayoutTypes'
    """
    e.g. rows, grid, measured distance
    May have a prescribed value for the number of axes in the layout e.g. for a 2D array, axes=2.
    Layouts may be applied to unit positions within a location
    """
    axes: int|None = None
