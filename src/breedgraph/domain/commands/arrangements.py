from .base import Command
from src.breedgraph.domain.model.controls import ReadRelease

from typing import List

class CreateLayout(Command):
    user: int
    release: str = ReadRelease.REGISTERED.name

    name: str
    type: int
    location: int
    axes: List[str]

    parent: int|None = None
    position: List[int|float|str]|None = None

class UpdateLayout(Command):
    user: int
    layout: int
    release: str

    name: str
    type: int
    location: int
    axes: List[str]

    parent: int | None
    position: List[int|float|str]|None = None

class DeleteLayout(Command):
    user: int
    layout: int