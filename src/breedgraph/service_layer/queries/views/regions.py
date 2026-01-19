from abc import ABC, abstractmethod

from src.breedgraph.domain.model.regions import LocationOutput
from src.breedgraph.service_layer.infrastructure import AbstractStateStore

from src.breedgraph.domain.model.regions import LocationInput
from typing import List, AsyncGenerator

class AbstractRegionsView(ABC):
    state_store: AbstractStateStore
    read_teams: List[int]

    async def countries(self) -> List[LocationInput]:
        return [country async for country in self.state_store.get_countries()]

    async def get_locations_by_type(self, location_type: int) -> List[LocationOutput]:
        return [location async for location in self._get_locations_by_type(location_type)]

    @abstractmethod
    def _get_locations_by_type(self, location_type: int) -> AsyncGenerator[LocationOutput, None]:
        ...