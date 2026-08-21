from .base import Command
from typing import List
from pydantic import model_validator
from breedgraph.domain.model.time_descriptors import PyDT64
from breedgraph.domain.model.controls import ReadRelease

from breedgraph.custom_exceptions import IllegalOperationError

class CreateUnit(Command):
    agent_id: int
    write_team: int | None = None
    release: ReadRelease = ReadRelease.PRIVATE

    name: str | None = None
    description: str | None = None

    subject_id: int | None = None
    germplasm_id: int | None = None

    parents: List[int] | None = None
    children: List[int] | None = None

    # Position details, require location_id if no parents are provided
    location_id: int|None = None
    layout_id: int|None = None
    coordinates: List[str|int|float]|None = None

    start: PyDT64|None = None
    end: PyDT64|None = None



class UpdateUnit(Command):
    agent_id: int
    unit_id: int

    name: str | None = None
    description: str | None = None

    subject_id: int | None = None
    germplasm_id: int | None = None

    parents: List[int] | None = None
    children: List[int] | None = None


class DeleteUnit(Command):
    agent_id: int
    unit_id: int

class AddPosition(Command):
    agent_id: int

    unit_id: int

    location_id: int
    layout_id: int|None = None
    coordinates: List[str|int|float]|None = None

    start: PyDT64|None = None
    end: PyDT64|None = None

class RemovePosition(Command):
    agent_id: int
    unit_id: int

    location_id: int
    layout_id: int|None = None
    coordinates: List[str|int|float]|None = None

    start: PyDT64|None = None
    end: PyDT64|None = None

