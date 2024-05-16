"""
This is akin to the observation unit from BrAPI

With trees these are long-lived and may be shared across studies,
but we also have field level down to sample and sub-sample observations.

With BreedCAFS "item" concept we supported pooling/splitting of samples only.

This time we keep it flexible from the beginning,
 with parent/child and a specified Subject from the ontology (tree,leaf etc.)
"""
from pydantic import BaseModel, field_validator, ValidationError

from src.breedgraph.domain.model.layouts import Position

from src.breedgraph.adapters.repositories.base import Entity, Aggregate, AggregateRoot

from typing import List

class Unit(BaseModel):
    subject: int  # ref to SubjectTypeStored

    # if any values for variables/conditions/events are recorded then store true, can no longer be removed.
    used: bool = False

    # Optional details:
    name: str|None = None
    code: str|None = None
    description: str|None = None

    # In BreedCAFS we had to store observations made on a field with mixed germplasm
    germplasm: List[int] # refs to GermplasmEntryStored

    location: int|None = None # ref to LocationStored

    layout: int|None = None # ref to LayoutStored
    position: Position|None = None

    studies: List[int]  # Study ID can be used to find the relevant investigations/programs
    events: List[int]  # Event ID to find history of events for this unit
    conditions: List[int]  # Condition ID to find conditions for this unit
    variables: List[int]  # Variable ID associated with this unit

    parents: List[int]  # must support multiple parents, for example when pooling samples.
    children: List[int]

class UnitStored(Unit, Entity):
    pass

class UnitRoot(Unit, AggregateRoot):

    @field_validator
    def validate_parents(cls, value):
        if value:
            raise ValidationError("Unit root should have no parents")

class UnitTree(Aggregate):
    units: List[Unit|UnitRoot]

    @property
    def root(self) -> UnitRoot:
        return self.units[0]

    @property
    def protected(self) -> str | False:
        for u in self.units:
            if u.used:
                return "At least one unit within this UnitTree is referenced, cannot remove the whole UnitTree"
        return False
