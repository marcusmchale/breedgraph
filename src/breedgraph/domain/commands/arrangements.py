from .base import Command

from typing import List

from breedgraph.domain.model.controls import ReadRelease


class CreateLayout(Command):
    agent_id: int
    write_team: int | None = None
    release: ReadRelease = ReadRelease.PRIVATE

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