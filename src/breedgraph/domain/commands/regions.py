from .base import Command

from typing import List
from typing_extensions import TypedDict

class GeoCoordinate(TypedDict):  #ISO 6709
    latitude: float
    longitude: float
    altitude: float|None
    uncertainty: float|None
    description: str|None

class AddLocation(Command):
    user: int

    name: str
    type: int

    fullname: str = None
    description: str = None
    code: str = None
    address: str = None
    coordinates: List[GeoCoordinate]

    parent: int|None = None

class RemoveLocation(Command):
    user: int
    location: int

class UpdateLocation(Command):
    user: int
    location: int

    name: str
    type: int

    fullname: str = None
    description: str = None
    code: str = None
    address: str = None
    coordinates: List[GeoCoordinate]

    parent: int | None = None