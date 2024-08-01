from src.breedgraph.domain.model.ontology.entries import OntologyEntry
from typing import ClassVar

class Design(OntologyEntry):
    """
    To describe types of experimental design
    """
    label: ClassVar[str] = 'Design'
    plural: ClassVar[str] = 'Designs'