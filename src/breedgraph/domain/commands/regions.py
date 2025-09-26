from .base import Command

from typing import List
from typing_extensions import TypedDict

class GeoCoordinate(TypedDict):  #ISO 6709
    latitude: float
    longitude: float
    altitude: float|None
    uncertainty: float|None
    description: str|None

class CreateLocation(Command):
    agent_id: int

    type_id: int
    name: str

    fullname: str = None
    description: str = None
    code: str = None
    address: str = None
    coordinates: List[GeoCoordinate] = None

    parent_id: int|None = None

class UpdateLocation(Command):
    agent_id: int
    location_id: int

    type_id: int
    name: str

    fullname: str
    description: str
    code: str
    address: str
    coordinates: List[GeoCoordinate]

    parent_id: int | None

class DeleteLocation(Command):
    agent_id: int
    location_id: int