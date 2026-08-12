from pydantic import BaseModel

from breedgraph.domain.model.controls import ReadRelease

from .base import Command


class GeoCoordinate(BaseModel):  #ISO 6709
    latitude: float
    longitude: float
    altitude: float|None = None
    uncertainty: float|None = None
    description: str|None = None

class CreateLocation(Command):
    agent_id: int
    write_team: int | None = None
    release: ReadRelease = ReadRelease.PRIVATE

    type_id: int
    name: str

    fullname: str = None
    description: str = None
    code: str = None
    address: str = None
    coordinates: list[GeoCoordinate] = None

    parent_id: int|None = None

class UpdateLocation(Command):
    agent_id: int
    location_id: int

    type_id: int|None = None
    name: str|None = None

    fullname: str|None = None
    description: str|None = None
    code: str|None = None
    address: str|None = None
    coordinates: list[GeoCoordinate]|None = None

    parent_id: int|None = None

class DeleteLocation(Command):
    agent_id: int
    location_id: int