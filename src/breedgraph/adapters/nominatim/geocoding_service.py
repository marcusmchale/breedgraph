import asyncio
import time
from typing import List

import httpx

from breedgraph import config
from breedgraph.custom_exceptions import IllegalOperationError
from breedgraph.service_layer.infrastructure.geocoding import AbstractGeocodingService, Place

import logging
logger = logging.getLogger(__name__)


class NominatimGeocodingService(AbstractGeocodingService):
    """
    Nominatim's search API (config.geocoding), asked from the server at most once a second in each process, as its
    usage policy requires. Searches are not logged.
    """

    def __init__(self):
        self._lock = asyncio.Lock()
        self._last_request = 0.0

    @staticmethod
    def _headers() -> dict:
        contact = f" ({config.MAIL_FROM})" if config.MAIL_FROM else ""
        return {'User-Agent': f"BreedGraph{contact}", 'Accept': 'application/json'}

    async def _search(self, params: dict) -> list:
        async with self._lock:
            wait = self._last_request + 1 - time.monotonic()
            if wait > 0:
                await asyncio.sleep(wait)
            try:
                async with httpx.AsyncClient(timeout=10) as client:
                    response = await client.get(
                        f"{config.NOMINATIM_URL}/search", params={**params, 'format': 'json'}, headers=self._headers()
                    )
            except httpx.HTTPError as e:
                logger.warning(f"Place search failed: {type(e).__name__}")
                raise IllegalOperationError("Place search is not available, please try again later")
            finally:
                self._last_request = time.monotonic()
        if response.status_code != 200:
            logger.warning(f"Place search failed with status {response.status_code}")
            raise IllegalOperationError("Place search is not available, please try again later")
        return response.json()

    @staticmethod
    def _place(result: dict) -> Place:
        bounds = None
        box = result.get('boundingbox')  # [south, north, west, east]
        if box and len(box) == 4:
            south, north, west, east = (float(value) for value in box)
            bounds = [[south, west], [north, east]]
        return Place(
            name=result.get('display_name') or '',
            latitude=float(result['lat']),
            longitude=float(result['lon']),
            bounds=bounds
        )

    async def search_places(
            self,
            query: str,
            viewbox: List[float] | None = None,
            bounded: bool = False,
            country_code: str | None = None,
            limit: int = 5
    ) -> List[Place]:
        query = (query or '').strip()
        if not query:
            return []
        params = {'q': query, 'limit': max(1, min(limit, 20))}
        if viewbox:
            if len(viewbox) != 4:
                raise IllegalOperationError("A viewbox is [west, south, east, north]")
            params['viewbox'] = ','.join(str(value) for value in viewbox)
            if bounded:
                params['bounded'] = 1
        if country_code:
            params['countrycodes'] = country_code.casefold()
        return [self._place(result) for result in await self._search(params)]

    async def geocode_country(self, name: str) -> Place | None:
        name = (name or '').strip()
        if not name:
            return None
        results = await self._search({'country': name, 'limit': 1})
        return self._place(results[0]) if results else None
