from abc import ABC
from dataclasses import dataclass, field, replace

from src.breedgraph.service_layer.tracking.wrappers import asdict
from src.breedgraph.domain.model.base import EnumLabeledModel, StoredModel
from src.breedgraph.domain.model.controls import ControlledModel, ControlledTreeAggregate, Controller, ControlledModelLabel

from typing import List, ClassVar, Dict, Any

@dataclass
class GeoCoordinate:  # ISO 6709
    latitude: float
    longitude: float
    altitude: float = None
    uncertainty: float = None
    description: str = None

@dataclass
class LocationBase(ABC):
    label: ClassVar[ControlledModelLabel] = ControlledModelLabel.LOCATION

    name: str = None
    fullname: str = None
    synonyms: List[str] = field(default_factory=list)
    type: int|None = None  # reference to location type in ontology

    description: str|None = None
    code: str|None = None  # can be country code, zip code, code for a field etc.
    address: str|None = None

    coordinates: list[GeoCoordinate]|None = field(default_factory=list)
    # if more than one coordinate then interpret as a polygon specifying boundaries
    # todo consider: what about lines, e.g. two then a line, but other lines? needed? not for location

    @property
    def names(self):
        return [self.name] + self.synonyms

    def __hash__(self):
        return hash(self.name)


@dataclass
class LocationInput(LocationBase, EnumLabeledModel):
    pass

@dataclass
class LocationStored(LocationBase, ControlledModel):

    def redacted(
            self,
            controller: Controller,
            user_id = None,
            read_teams = None
    ):
        return replace(
            self,
            type = None,
            name = self.redacted_str,
            synonyms = [self.redacted_str for _ in self.synonyms],
            description = self.description and self.redacted_str,
            code = self.code and self.redacted_str,
            address = self.address and self.redacted_str,
            coordinates = list()
        )

@dataclass
class LocationOutput(LocationBase, StoredModel, EnumLabeledModel):
    parent: int | None = None
    children: list[int] = field(default_factory=list)


TInput=LocationInput
TStored=LocationStored
class Region(ControlledTreeAggregate):
    default_edge_label: ClassVar['str'] = "INCLUDES_LOCATION"

    def add_location(self, location: LocationInput, parent_id: int|None):
        if parent_id is not None:
            sources = {parent_id: None}
        else:
            sources = None

        return super().add_entry(location, sources)

    def get_location(self, location: str|int) -> LocationInput|LocationStored:
        return super().get_entry(location)

    def to_output_map(self) -> dict[int, LocationOutput]:
        return {node: LocationOutput(
            **self.get_location(node).model_dump(),
            parent=self.get_parent_id(node),
            children=self.get_children_ids(node)
        ) for node in self._graph}

    def yield_locations_by_type(self, type_id: int):
        for e in self.entries.values():
            if e.type == type_id:
                yield e
