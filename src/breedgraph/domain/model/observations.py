from pydantic import BaseModel
from typing import List

from src.breedgraph.domain.model.accounts import AccountStored
from src.breedgraph.domain.model.base import StoredEntity
from src.breedgraph.domain.model.regions import GeoCoordinate
from src.breedgraph.domain.model.time_descriptors import TimeDescriptor
from src.breedgraph.domain.model.controls import ControlledInput, ControlledModel, ControlledAggregate

class ObservationBase(BaseModel):
    variable: int
    unit: int
    study: int

    value: str | int | float
    time: TimeDescriptor
    coordinates: GeoCoordinate|None = None

    collectors: List[int]  # reference to PersonStored

class ObservationInput(ControlledInput):
    pass

class ObservationStored(ControlledModel):
    def redacted(self, account: AccountStored) -> 'ObservationStored|None':
        if not self.controller.can_read(account):

            if not account:
                return None

            observation: ObservationStored = self.model_copy()
            observation.collectors = list()
            observation.value = None
            observation.coordinates = None

            return observation

        else:
            return self

    @property
    def root(self) -> ControlledModel:
        return self

    @property
    def protected(self) -> str | None:
        return None
