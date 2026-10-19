from typing import List

from .base import Event


class CountryAdded(Event):
    location_id: int
    code: str
    agent_id: int


class LocationPlaced(Event):
    """Coordinates were set on a location below a country"""
    location_id: int
    agent_id: int


class CountryRemoved(Event):
    code: str


# Detailed map tiles (adapters/pmtiles/map_regions.py), to tell the users who asked for them

class MapRegionFetching(Event):
    name: str
    user_ids: List[int]


class MapCountryDivided(Event):
    name: str
    user_ids: List[int]


class MapRegionReady(Event):
    name: str
    user_ids: List[int]


class MapRegionFailed(Event):
    name: str
    user_ids: List[int]
