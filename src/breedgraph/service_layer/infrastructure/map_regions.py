"""
Detailed map tiles for regions (README.md, Maps): a country's when it is added, or for a country too large to fetch
whole, a section's when a location in it is placed on the map. Fetching runs in the background, and the users who asked
are emailed when it starts and ends.
"""
from abc import ABC, abstractmethod
from typing import Iterable, Tuple


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
    async def request_country(self, code: str, requested_by: int | None = None) -> None:
        """Fetch the country with this ISO 3166 alpha-3 code, or divide it when it is too large"""
        ...

    @abstractmethod
    async def request_places(
            self,
            code: str,
            coordinates: Iterable[Tuple[float, float]],
            requested_by: int | None = None
    ) -> None:
        """Fetch what is needed to map these points (latitude, longitude) in the country"""
        ...

    @abstractmethod
    async def remove_country(self, code: str) -> None:
        """Delete the country's regions"""
        ...
