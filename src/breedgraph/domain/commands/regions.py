from .base import Command

from src.breedgraph.domain.model.controls import ReadRelease

from typing import List
from typing_extensions import TypedDict

class GeoCoordinate(TypedDict):  #ISO 6709
    latitude: float
    longitude: float
    altitude: float|None
    uncertainty: float|None
    description: str|None

class CreateLocation(Command):
    user: int
    release: str = ReadRelease.REGISTERED.name

    name: str
    type: int
    fullname: str = None
    description: str = None
    code: str = None
    address: str = None
    coordinates: List[GeoCoordinate] = None

    parent: int|None = None

class UpdateLocation(Command):
    user: int
    location: int

    name: str
    type: int

    fullname: str
    description: str
    code: str
    address: str
    coordinates: List[GeoCoordinate]

    parent: int | None
    release: str

class DeleteLocation(Command):
    user: int
    location: int