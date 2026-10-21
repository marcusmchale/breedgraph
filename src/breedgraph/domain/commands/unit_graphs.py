from .base import Command
from typing import List
from pydantic import BaseModel, model_validator
from breedgraph.domain.model.time_descriptors import PyDT64
from breedgraph.domain.model.controls import ReadRelease

from breedgraph.custom_exceptions import IllegalOperationError

class CreateUnit(Command):
    agent_id: int
    write_team: int
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

    # unchanged unless set, and set to None to remove (model_fields_set)
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



class ArrivalOfUnits(BaseModel):
    """An arrival as given: its location and start as entered, and a unit to take only those at, below or above it"""
    location_id: int
    start: PyDT64 | None = None
    unit_id: int | None = None


class UnitsSelection(BaseModel):
    """The units by id, or the units of an arrival that the user can read; one of the two"""
    unit_ids: List[int] | None = None
    arrival: ArrivalOfUnits | None = None


class PositionFields(BaseModel):
    """Values of a position as given: those not given are told apart from those given as null (model_fields_set)"""
    location_id: int | None = None
    layout_id: int | None = None
    coordinates: List[str|int|float] | None = None
    start: PyDT64 | None = None
    end: PyDT64 | None = None

    def given(self) -> dict:
        return {name: getattr(self, name) for name in self.model_fields_set}


class MoveUnits(Command):
    """Moves the units to a position from its start; returns the ids of the units moved"""
    agent_id: int
    units: UnitsSelection

    location_id: int
    layout_id: int | None = None
    coordinates: List[str|int|float] | None = None

    start: PyDT64 | None = None
    end: PyDT64 | None = None


class ChangePositions(Command):
    """Changes one position of each unit, found by the values in at; returns the ids of the units changed"""
    agent_id: int
    units: UnitsSelection
    at: PositionFields
    change: PositionFields
