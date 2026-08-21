from .base import Command

from typing import List

from breedgraph.domain.model.controls import ReadRelease


class CreateLayout(Command):
    agent_id: int
    write_team: int | None = None
    release: ReadRelease = ReadRelease.PRIVATE

    type_id: int
    location_id: int|None = None


    name: str|None
    axes: List[str]

    parent: int|None = None
    position: List[int|float|str]|None = None

    def __post_init__(self):
        if self.location_id and not self.parent is None:
            raise ValueError("Cannot provide location for non-root layout")
        if self.parent is None and self.location_id is None:
            raise ValueError("Must provide location for root layout")

class UpdateLayout(Command):
    agent_id: int
    layout_id: int

    location_id: int | None
    type_id: int

    name: str|None
    axes: List[str]

    parent: int | None
    position: List[int|float|str]|None = None

    def __post_init__(self):
        if self.location_id and not self.parent is None:
            raise ValueError("Cannot provide location for non-root layout")
        if self.parent is None and self.location_id is None:
            raise ValueError("Must provide location for root layout")

class DeleteLayout(Command):
    agent_id: int
    layout_id: int