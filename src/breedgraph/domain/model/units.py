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

from src.breedgraph.domain.model.base import StoredEntity, Aggregate


from typing import List

class Unit(BaseModel):
    subject: int  # ref to SubjectTypeStored

    # if any values for variables/conditions/events are recorded then store true, can no longer be removed.
    used: bool = False

    # Optional details:
    name: str|None = None
    code: str|None = None
    description: str|None = None

    germplasm: List[int] # refs to GermplasmEntryStored

    location: int|None = None # ref to LocationStored

    layout: int|None = None # ref to LayoutStored
    position: Position|None = None

    studies: List[int]  # Study ID can be used to find the relevant investigations/programs

    parameters: List[int]  # Condition ID to find conditions for this unit
    variables: List[int]  # Variable ID associated with this unit
    events: List[int]  # Event ID to find history of events for this unit

    parents: List[int]  # must support multiple parents,
      # for example when pooling samples or making observations on a group of trees within a field
      # In Breedcafs we saw this when harvest needed to be pooled for assessment.
      #   Here the unit is derived from multiple parent units that are described elsewhere
    children: List[int]

class UnitStored(Unit, StoredEntity):
    pass

class UnitTree(Aggregate):
    units: List[Unit]

    @property
    def root(self) -> Unit:
        return self.units[0]

    @property
    def protected(self) -> str | False:
        for u in self.units:
            if u.used:
                return "At least one unit within this UnitTree is referenced, cannot remove the whole UnitTree"
        return False
