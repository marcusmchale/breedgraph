from abc import ABC, abstractmethod
from typing import AsyncGenerator

from src.breedgraph.domain.model.controls import Access
from src.breedgraph.domain.model.regions import LocationOutput
from src.breedgraph.service_layer.application import AbstractAccessControlService

from typing import Dict, Set

class AbstractRegionsViews(ABC):
    access_control: AbstractAccessControlService

    @abstractmethod
    def get_locations_by_type(self, location_type: int) -> AsyncGenerator[LocationOutput, None]:
        ...
