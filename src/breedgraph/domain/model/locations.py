from pydantic import BaseModel, field_validator, ValidationError, Field, computed_field
import re

from src.breedgraph.domain.model.base import Entity, Aggregate


from typing import List


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

class Facility(Location):
    type: int  # reference to facility type in ontology


class Region(BaseModel):

    locations: List[Location]

    def __hash__(self):
        return hash(self.root.code)

    @computed_field
    @property
    def root(self) -> Location:
        # get from view but allow new according to ISO_3166-1_alpha-3
        # https://en.wikipedia.org/wiki/ISO_3166-1_alpha-3
        return self.locations[0]

    @field_validator('locations')
    def validate_code(cls, v):
        country = v[0]
        code = country.code
        if not len(code) == 3 and re.match('[A-Z][A-Z][A-Z]', code):
            raise ValidationError("Region root node must be a country, i.e. have a code from iso3166-1 alpha 3")
