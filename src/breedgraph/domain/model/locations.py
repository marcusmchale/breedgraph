from pydantic import BaseModel, field_validator
from geojson import Point, Polygon

from src.breedgraph.domain.model.ontologies import Ontology
from src.breedgraph.domain.model.references import Reference

class Coordinate(BaseModel):
    geometry: None #Point|Polygon
    uncertainty: float = None
    description: str = None

class Country(BaseModel):
    # get from view but allow new according to ISO_3166-1_alpha-3

    name: str
    code: str

class Location(BaseModel):
    name: str
    fullname: str = None
    description: str = None

    coordinate: Coordinate = None
    country: Country


    address: str
    city: str
    state: str
    zip: str
    country: str


class GrowthFacilityType(BaseModel):
    name: str
    description: str
    ontology: Ontology

class GrowthFacilityTypeStored(GrowthFacilityType):
    id: int

class GrowthFacility(BaseModel):
    name: str
    description: str
    ontology: Reference
    type: GrowthFacilityType
    location: Location

class StoredGrowthFacility(GrowthFacility):
    id: int

