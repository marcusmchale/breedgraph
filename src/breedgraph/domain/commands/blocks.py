from .base import Command
from typing import List, Any
from src.breedgraph.domain.model.controls import ReadRelease
from src.breedgraph.domain.model.time_descriptors import PyDT64

class CreateUnit(Command):
    user: int
    subject: int
    parents: List[int] | None = None
    children: List[int] | None = None
    name: str | None = None
    synonyms: List[str] | None = None
    description: str | None = None
    release: str = ReadRelease.REGISTERED.name

class UpdateUnit(Command):
    user: int
    unit_id: int
    subject: int | None = None
    parents: List[int] | None = None
    children: List[int] | None = None
    name: str | None = None
    synonyms: List[str] | None = None
    description: str | None = None
    release: str | None = None

class DeleteUnit(Command):
    user: int
    unit_id: int

class AddPosition(Command):
    user: int
    unit: int
    location: int
    layout: int=None
    coordinates: List[str|int|float]=None
    start: PyDT64|None = None
    end: PyDT64|None = None
