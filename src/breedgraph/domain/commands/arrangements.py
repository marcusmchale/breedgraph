from .base import Command

from typing import List

class CreateLayout(Command):
    agent_id: int

    location_id: int
    type_id: int

    name: str|None
    axes: List[str]

    parent: int|None = None
    position: List[int|float|str]|None = None

class UpdateLayout(Command):
    agent_id: int
    layout_id: int

    location_id: int
    type_id: int

    name: str|None
    axes: List[str]

    parent: int | None
    position: List[int|float|str]|None = None

class DeleteLayout(Command):
    agent_id: int
    layout_id: int