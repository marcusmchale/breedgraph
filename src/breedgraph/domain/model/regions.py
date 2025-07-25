from pydantic import BaseModel

from src.breedgraph.domain.model.base import LabeledModel
from src.breedgraph.domain.model.controls import ControlledModel, ControlledTreeAggregate, ReadRelease

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

    coordinates: list[GeoCoordinate]|None = list() # if more than one then interpreted as a polygon specifying boundaries

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

class LocationOutput(LocationStored):
    parent: int | None
    children: list[int]
    release: ReadRelease

class Region(ControlledTreeAggregate):

    def add_location(self, location: LocationInput, parent_id: int|None):
        if parent_id is not None:
            sources = {parent_id: None}
        else:
            sources = None

        return super().add_entry(location, sources)

    def get_location(self, location: str|int):
        return super().get_entry(location)

    def to_output_map(self) -> dict[int, LocationOutput]:
        return {node: LocationOutput(
            **self.get_location(node).model_dump(),
            parent=self.get_parent_id(node),
            children=self.get_children_ids(node),
            release=self.get_location(node).controller.release
        ) for node in self._graph}

    def yield_locations_by_type(self, type_id: int):
        for e in self.entries.values():
            if e.type == type_id:
                yield e
