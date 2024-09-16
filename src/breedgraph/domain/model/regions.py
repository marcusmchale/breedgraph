from pydantic import BaseModel

from src.breedgraph.domain.model.base import LabeledModel
from src.breedgraph.domain.model.controls import ControlledModel, ControlledTreeAggregate

from typing import List, ClassVar

class GeoCoordinate(BaseModel):  # ISO 6709
    latitude: float
    longitude: float
    altitude: float = None
    uncertainty: float = None
    description: str = None

class LocationBase(LabeledModel):
    label: ClassVar[str] = 'Location'
    plural: ClassVar[str] = 'Locations'

    name: str
    synonyms: List[str] = list()
    type: int  # reference to location type in ontology

    description: str|None = None
    code: str|None = None  # can be country code, zip code, code for a field etc.
    address: str|None = None

    coordinates: list[GeoCoordinate] = list() # if more than one then interpreted as a polygon specifying boundaries

    @property
    def names(self):
        return [self.name] + self.synonyms

    def __hash__(self):
        return hash(self.name)

class LocationInput(LocationBase):
    pass

class LocationStored(LocationBase, ControlledModel):

    def redacted(self):
        return self.model_copy(deep=True, update={
            'name': self.redacted_str,
            'synonyms': [self.redacted_str for _ in self.synonyms],
            # type is still visible, this node is only seen when root of aggregate.
            'description': self.redacted_str if self.description is not None else self.description,
            'code': self.redacted_str if self.code is not None else self.code,
            'address': self.redacted_str if self.address is None else self.address,
            'coordinates': list()
        })

class Region(ControlledTreeAggregate):

    def add_location(self, location: LocationInput, parent_id: int|None):
        if parent_id is not None:
            sources = {parent_id: None}
        else:
            sources = None

        return super().add_entry(location, sources)

    def get_location(self, location: str|int):
        return super().get_entry(location)
