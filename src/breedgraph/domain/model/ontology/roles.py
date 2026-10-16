from dataclasses import dataclass
from breedgraph.domain.model.ontology.entries import (
    OntologyEntryBase, OntologyEntryInput, OntologyEntryStored
)
from breedgraph.domain.model.ontology.enums import OntologyEntryLabel

from typing import ClassVar

@dataclass
class RoleBase(OntologyEntryBase):
    label: ClassVar[OntologyEntryLabel] = OntologyEntryLabel.ROLE
    """
    The role a Person had in a contribution, e.g. Investigation, Data curation.
    Based on CRediT, extended where needed (docs/contributions.md).
    Roles describe contributions, never Persons.
    """

@dataclass
class RoleInput(RoleBase, OntologyEntryInput):
    pass

@dataclass
class RoleStored(RoleBase, OntologyEntryStored):
    pass
