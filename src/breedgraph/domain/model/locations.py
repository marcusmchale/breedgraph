from pydantic import BaseModel, field_validator, ValidationError, Field, computed_field
import re

from src.breedgraph.domain.model.base import Entity, Aggregate


from typing import List, Dict


class Coordinate(BaseModel):
    latitude: float
    longitude: float
    altitude: float = None
    uncertainty: float = None
    description: str = None

class Location(BaseModel):
    type: int  # reference to location type in ontology

    name: str
    fullname: str = None
    description: str = None
    code: str = None  # can be country code, zip code, code for a field etc.

    coordinates: list[Coordinate] = None # if more than one then interpreted as a polygon specifying boundaries
    address: str = None

    parent: int = None
    children: None | List[int] = Field(frozen=True)


class LocationStored(Location, Entity):
    id: int


class Region(Aggregate):
    root_id: int
    locations: Dict[int, Location|LocationStored]

    @classmethod
    def from_list(cls, locations_list: List[LocationStored]):
        root_id = None
        teams_map = dict()
        for team in teams_list:
            teams_map[team.id] = team
            if team.parent is None:
                root_id = team.id
        return cls(root_id=root_id, teams=teams_map)


    @property
    def root(self) -> LocationStored:
        return self.locations[self.root_id]

    @property
    def protected(self) -> str|None:
        if self.root.children:
            return "Cannot delete an organisation while its root has children"


    @field_validator('locations')
    def validate_code(cls, v):
        country = v[0]
        code = country.code
        if not len(code) == 3 and re.match('[A-Z][A-Z][A-Z]', code):
            raise ValidationError("Region root node must be a country, i.e. have a code from iso3166-1 alpha 3")
