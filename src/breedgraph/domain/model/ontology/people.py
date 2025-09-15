from dataclasses import dataclass, field
from src.breedgraph.domain.model.ontology.entries import (
    OntologyEntryBase, OntologyEntryInput, OntologyEntryStored, OntologyEntryOutput
)
from typing import ClassVar

@dataclass
class RoleBase(OntologyEntryBase):
    label: ClassVar[str] = 'Role'
    plural: ClassVar[str] = 'Roles'
    """
    e.g. Scientist, Admin etc.
    """

@dataclass
class RoleInput(RoleBase, OntologyEntryInput):
    pass

@dataclass
class RoleStored(RoleBase, OntologyEntryStored):
    pass

@dataclass
class RoleOutput(RoleBase, OntologyEntryOutput):
    terms: list[int] = field(default_factory=list)

@dataclass
class TitleBase(OntologyEntryBase):
    label: ClassVar[str] = 'Title'
    plural: ClassVar[str] = 'Titles'
    """
    e.g. Mr, Ms, Dr etc.
    """

@dataclass
class TitleInput(TitleBase, OntologyEntryInput):
    pass

@dataclass
class TitleStored(TitleBase, OntologyEntryStored):
    pass

@dataclass
class TitleOutput(TitleBase, OntologyEntryOutput):
    terms: list[int] = field(default_factory=list)