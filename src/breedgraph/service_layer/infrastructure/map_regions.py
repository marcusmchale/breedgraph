"""
Detailed map tiles for regions (README.md, Maps): a country's when it is added, or for a country too large to fetch
whole, a section's when a location in it is placed on the map. Fetching runs in the background, and where it stands
is asked for by BreedView's location map (status), which says so under the map.
"""
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from enum import Enum
from typing import Iterable, List, Tuple


class MapState(str, Enum):
    NONE = 'NONE'  # never asked for, or asked for where detailed maps are not fetched
    PENDING = 'PENDING'  # asked for: its outline found and its size measured before it is fetched
    FETCHING = 'FETCHING'  # its file being cut
    READY = 'READY'
    DIVIDED = 'DIVIDED'  # a country too large to fetch whole, fetched by its sections
    FAILED = 'FAILED'


@dataclass
class MapSectionStatus:
    """A section of a divided country, such as a state or province"""
    name: str
    state: MapState
    size: int | None = None  # in bytes, once measured
    error: str | None = None  # why it could not be fetched, for its users


@dataclass
class CountryMapStatus:
    code: str
    state: MapState
    limit: int  # in bytes: the size above which a country is divided, and a section is not fetched
    enabled: bool  # whether this site fetches detailed maps
    size: int | None = None
    error: str | None = None
    sections: List[MapSectionStatus] = field(default_factory=list)


class AbstractMapRegions(ABC):

    @abstractmethod
    async def start(self) -> None:
        """Resume fetches interrupted by a restart"""
        ...

    @abstractmethod
    async def stop(self) -> None:
        """Stop fetching; unfinished fetches resume at the next start"""
        ...

    @abstractmethod
    async def request_country(self, code: str) -> None:
        """Fetch the country with this ISO 3166 alpha-3 code, or divide it when it is too large"""
        ...

    @abstractmethod
    async def request_places(self, code: str, coordinates: Iterable[Tuple[float, float]]) -> None:
        """Fetch what is needed to map these points (latitude, longitude) in the country"""
        ...

    @abstractmethod
    async def remove_country(self, code: str) -> None:
        """Delete the country's regions"""
        ...

    @abstractmethod
    async def status(self, code: str) -> CountryMapStatus:
        """Where the country's detailed maps stand, and those of its sections when it is divided"""
        ...
