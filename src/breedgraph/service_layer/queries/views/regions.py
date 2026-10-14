from abc import ABC, abstractmethod

from breedgraph.domain.model.regions import LocationOutput
from breedgraph.service_layer.infrastructure import AbstractStateStore

from breedgraph.domain.model.regions import LocationInput
from typing import List, Dict, Iterable, AsyncGenerator

class AbstractRegionsView(ABC):
    """
    Locations as the user may see them (see query_builders.regions): readable locations in full, with hidden ones
    skipped in their region's tree, and placeholders only for hidden locations asked for directly or region roots
    holding readable locations.
    """
    state_store: AbstractStateStore
    user_id: int | None
    read_teams: List[int]

    async def countries(self) -> List[LocationInput]:
        return [country async for country in self.state_store.get_countries()]

    async def get_regions(self) -> List[LocationOutput]:
        """The root of every region the user can read a location in"""
        return await self._get_regions()

    @abstractmethod
    async def _get_regions(self) -> List[LocationOutput]:
        ...

    async def get_locations(self, location_ids: Iterable[int]) -> Dict[int, LocationOutput]:
        """The locations with these ids that exist, keyed by id, as placeholders where the user cannot read them"""
        location_ids = [location_id for location_id in dict.fromkeys(location_ids) if location_id is not None]
        if not location_ids:
            return {}
        return await self._get_locations(location_ids)

    @abstractmethod
    async def _get_locations(self, location_ids: List[int]) -> Dict[int, LocationOutput]:
        ...

    async def get_locations_by_type(self, location_type: int) -> List[LocationOutput]:
        return [location async for location in self._get_locations_by_type(location_type)]

    @abstractmethod
    def _get_locations_by_type(self, location_type: int) -> AsyncGenerator[LocationOutput, None]:
        ...

    async def get_descendants_by_type(self, location_ids: Iterable[int]) -> Dict[int | None, List[LocationOutput]]:
        """
        Every readable location below these locations, as id, name and type, keyed by location type id.
        For selecting all the locations of a type at once; locations the user cannot read are left out.
        """
        location_ids = [location_id for location_id in dict.fromkeys(location_ids) if location_id is not None]
        if not location_ids:
            return {}
        return await self._get_descendants_by_type(location_ids)

    @abstractmethod
    async def _get_descendants_by_type(self, location_ids: List[int]) -> Dict[int | None, List[LocationOutput]]:
        ...