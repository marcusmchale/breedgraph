from .base import Command
from typing import List
from pydantic import model_validator
from src.breedgraph.domain.model.time_descriptors import PyDT64
from ...custom_exceptions import IllegalOperationError


class CreateUnit(Command):
    agent_id: int

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

    """
    Units are retrieved either from their ID, their block, or their location.
    As such, we must ensure that where a unit has no parents (new block), it must have a position.
    The minimal requirement for a position is the location_id.
    """
    @model_validator(mode='after')
    def _has_location_if_not_parent(self):
        has_parents = bool(self.parents)
        if not has_parents:
            has_location = self.location_id is not None
            if not has_location:
                raise IllegalOperationError("New blocks must have a position")
        return self


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

