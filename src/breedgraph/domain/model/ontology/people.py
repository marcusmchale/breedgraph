from src.breedgraph.domain.model.ontology.entries import OntologyEntry
from typing import ClassVar

class Role(OntologyEntry):
    label: ClassVar[str] = 'Role'
    plural: ClassVar[str] = 'Roles'
    """
    e.g. Scientist, Admin etc.
    """

class Title(OntologyEntry):
    label: ClassVar[str] = 'Title'
    plural: ClassVar[str] = 'Titles'
    """
    e.g. Mr, Ms, Dr etc.
    """