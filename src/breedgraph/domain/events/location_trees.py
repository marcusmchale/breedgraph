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

