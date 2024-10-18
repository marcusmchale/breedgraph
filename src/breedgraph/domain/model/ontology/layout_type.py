from src.breedgraph.domain.model.ontology.entries import OntologyEntry
from src.breedgraph.domain.model.ontology.enums import AxisType

from typing import ClassVar, List

class LayoutType(OntologyEntry):
    label: ClassVar[str] = 'LayoutType'
    plural: ClassVar[str] = 'LayoutTypes'
    """
    e.g. rows, grid, measured distance
    Each axis type should be defined.
    """
    axes: List[AxisType]
