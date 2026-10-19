"""
Finding places by name for the location map. The server asks the geocoder, so visitors' browsers contact no third
party and the geocoder sees the search, not who made it.
"""
from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import List


@dataclass(frozen=True)
class Place:
    name: str
    latitude: float
    longitude: float
    bounds: List[List[float]] | None = None  # [[south, west], [north, east]]


class AbstractGeocodingService(ABC):

    @abstractmethod
    async def search_places(
            self,
            query: str,
            viewbox: List[float] | None = None,
            bounded: bool = False,
            country_code: str | None = None,
            limit: int = 5
    ) -> List[Place]:
        """
        Places matching the query, preferring those in viewbox ([west, south, east, north]), or only those there when
        bounded, and only those in the country with ISO alpha-2 country_code when given
        """
        ...

    @abstractmethod
    async def geocode_country(self, name: str) -> Place | None:
        """The country with this name"""
        ...
