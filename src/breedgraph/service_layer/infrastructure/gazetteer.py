"""
Finding places by name for the location map (docs/maps.md). The gazetteer answers from GeoNames' places kept on our
server: the towns of the world, and every place of the countries in the location trees, fetched when a country is
added. Visitors' browsers contact no third party, and no search leaves the server.
"""
from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import List

from .map_regions import MapState


@dataclass(frozen=True)
class Place:
    name: str
    latitude: float
    longitude: float
    bounds: List[List[float]] | None = None  # [[south, west], [north, east]]
    description: str | None = None  # what kind of place it is: "town", "farm", "mountain"…
    region: str | None = None  # the sections of its country it is in: "Kerry, Munster"
    country: str | None = None  # its country's name
    country_code: str | None = None  # its country's ISO 3166 alpha-3 code, as locations' countries have
    zoom: int | None = None  # the map's zoom to show it at, when it has no bounds


@dataclass
class PlacesStatus:
    """Where a country's own places stand, for the location map"""
    state: MapState  # NONE, PENDING, READY or FAILED
    enabled: bool  # whether this site fetches places
    towns: bool  # whether the world's towns are there, which stand in for a country's own places until they are
    error: str | None = None  # why they could not be fetched, for their users


class AbstractGazetteer(ABC):

    @abstractmethod
    async def start(self) -> None:
        """Make the places' database, and resume fetches interrupted by a restart"""
        ...

    @abstractmethod
    async def stop(self) -> None:
        """Stop fetching; unfinished fetches resume at the next start"""
        ...

    @abstractmethod
    async def request_country(self, code: str) -> None:
        """Fetch the places of the country with this ISO 3166 alpha-3 code"""
        ...

    @abstractmethod
    async def remove_country(self, code: str) -> None:
        """Delete the country's places, leaving the world's towns of it"""
        ...

    @abstractmethod
    async def search_places(
            self,
            query: str,
            viewbox: List[float] | None = None,
            bounded: bool = False,
            country: str | None = None,
            limit: int = 5
    ) -> List[Place]:
        """
        Places matching the query, preferring those in viewbox ([west, south, east, north]), or only those there when
        bounded, and only those in the country with this alpha-3 code when given
        """
        ...

    @abstractmethod
    async def country_place(self, code: str) -> Place | None:
        """The country with this alpha-3 code, with the extent of its main parts"""
        ...

    @abstractmethod
    async def status(self, code: str) -> PlacesStatus:
        ...

