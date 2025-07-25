from pydantic import Field

from src.breedgraph.domain.model.base import LabeledModel
from src.breedgraph.domain.model.controls import ControlledModel, ControlledTreeAggregate, ReadRelease
from typing import List, ClassVar


class LayoutBase(LabeledModel):
    label: ClassVar[str] = 'Layout'
    plural: ClassVar[str] = 'Layouts'

    type: int  # ref to LayoutTypeStored
    location: int # ref to LocationStored

    axes: list[str] = Field(frozen=True, default=['default'])
    # order of these elements correspond to position coordinate values
    # should not change after creation or units positions could not be reliably constructed
    # just delete and create a new one.
    name: str | None = None

    @property
    def names(self):
        return [self.name]

    def __hash__(self):
        return hash(self.name)


class LayoutInput(LayoutBase):
    pass

class LayoutStored(LayoutBase, ControlledModel):

    def redacted(self):
        return self.model_copy(deep=True, update={
            # type, location id and axes are visible
            'name': self.redacted_str if self.name is not None else self.name
        })
    pass

class LayoutOutput(LayoutStored):
    parent: int | None
    children: list[int]
    release: ReadRelease

class Arrangement(ControlledTreeAggregate):

    @property
    def protected(self) -> str | bool:
        for _, layout in self.entries.items():
            if layout.units:
                return "This arrangement is used to define existing units and so cannot be removed"
        return False

    def add_layout(self, layout: LayoutInput, parent_id: int|None, position: List[str]|None):
        if parent_id is None:
            # this inserts layout as new root for the arrangement
            sources = None
        else:
            parent_layout = self.get_layout(parent_id)
            if not parent_layout.location == layout.location:
                raise ValueError("All layouts in an arrangement should have the same location")

            if not len(position) == len(parent_layout.axes):
                raise ValueError("Position should have same length as the parent layout axes")

            sources = {parent_id: {'position': position}}

        return super().add_entry(layout, sources)

    def get_layout(self, layout: int):
        return super().get_entry(layout)

    def to_output_map(self) -> dict[int, LayoutOutput]:
        return {node: LayoutOutput(
            **self.get_layout(node).model_dump(),
            parent=self.get_parent_id(node),
            children=self.get_children_ids(node),
            release=self.get_layout(node).controller.release
        ) for node in self._graph}
