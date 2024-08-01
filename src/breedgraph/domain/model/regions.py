from pydantic import BaseModel, field_validator, ValidationError, Field, computed_field, model_serializer, field_serializer
import re

from src.breedgraph.domain.model.accounts import AccountStored
from src.breedgraph.domain.model.base import StoredEntity, TreeAggregate
from src.breedgraph.domain.model.controls import ControlledModel, ControlledAggregate

from src.breedgraph.adapters.repositories.trackable_wrappers import Tracked, TrackedSet, TrackedDict, TrackedList

from typing import List, Dict, ClassVar


class GeoCoordinate(BaseModel):  # ISO 6709
    latitude: float
    longitude: float
    altitude: float = None
    uncertainty: float = None
    description: str = None

class LocationBase(BaseModel):

    name: str
    type: int  # reference to location type in ontology

    fullname: str|None = None
    description: str|None = None
    code: str|None = None  # can be country code, zip code, code for a field etc.
    address: str|None = None

    coordinates: list[GeoCoordinate] = [] # if more than one then interpreted as a polygon specifying boundaries
    parent: int|None = None


class LocationInput(LocationBase, ControlledModel):
    pass

class LocationStored(LocationBase, ControlledModel):
    label: ClassVar[str] = 'Location'
    plural: ClassVar[str] = 'Locations'

    children: List[int] = Field(frozen=True)

class Region(TreeAggregate, ControlledAggregate):

    def redact(self, account: AccountStored):
        for key, member in self.nodes.items():
            if isinstance(member, LocationStored):
                if not member.controller.can_read(account):
                    self.nodes[key] = None

    nodes: Dict[int, LocationInput | LocationStored | None]
