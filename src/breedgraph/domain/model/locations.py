from pydantic import BaseModel, field_validator, ValidationError, Field, computed_field
from geojson import Point, Polygon
import re

from src.breedgraph.domain.model.ontologies import OntologyEntry
from src.breedgraph.domain.model.references import Reference

from typing import List

class LocationType(BaseModel):
    name: str
    description: str
    ontology: OntologyEntry

class LocationTypeStored(LocationType):
    id: int
#todo system to store ontologyreference, locationtype etc.
# get from view but allow new according to ISO_3166-1_alpha-3
    # https://en.wikipedia.org/wiki/ISO_3166-1_alpha-3

class Coordinate(BaseModel):
    latitude: float
    longitude: float
    altitude: float = None
    uncertainty: float = None
    description: str = None

class Location(BaseModel):
    type: int  # reference to location type stored id, includes ontology for the code if provided
    code: str = None

    name: str
    fullname: str = None
    description: str = None

    coordinates: list[Coordinate] = None # if more than one then this is a polygon specifying the boundaries
    address: str = None

    parent: int = None
    children: None | List[int] = Field(frozen=True)

class LocationStored(Location):
    id: int

class Country(BaseModel):

    locations: List[Location]

    def __hash__(self):
        return hash(self.root.code)

    @computed_field
    @property
    def root(self) -> Location:
        return self.locations[0]
    @field_validator('locations')
    def validate_code(cls, v):
        country = v[0]
        code = country.code
        if not len(code) == 3 and re.match('[A-Z][A-Z][A-Z]', code):
            raise ValidationError("Country root node must have a code from iso3166-1 alpha 3")
