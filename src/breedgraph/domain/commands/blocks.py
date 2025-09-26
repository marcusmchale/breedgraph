from .base import Command
from typing import List
from src.breedgraph.domain.model.time_descriptors import PyDT64

class CreateUnit(Command):
    agent_id: int

    name: str | None = None
    synonyms: List[str] | None = None
    description: str | None = None

    subject_id: int | None = None
    parents: List[int] | None = None
    children: List[int] | None = None

class UpdateUnit(Command):
    agent_id: int
    unit_id: int

    name: str | None = None
    synonyms: List[str] | None = None
    description: str | None = None

    subject_id: int | None = None
    parents: List[int] | None = None
    children: List[int] | None = None


class DeleteUnit(Command):
    agent_id: int
    unit_id: int

class AddPosition(Command):
    agent_id: int
    unit_id: int

    location_id: int
    layout_id: int = None
    coordinates: List[str|int|float] = None

    start: PyDT64|None = None
    end: PyDT64|None = None
