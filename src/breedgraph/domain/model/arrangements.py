from dataclasses import field

import networkx as nx
import copy

from pydantic import field_validator, Field, field_serializer
from src.breedgraph.domain.model.base import LabeledModel
from src.breedgraph.domain.model.controls import ControlledModel, ControlledTreeAggregate
from typing import List, ClassVar, Set


class LayoutBase(LabeledModel):
    label: ClassVar[str] = 'Layout'
    plural: ClassVar[str] = 'Layouts'

    type: int  # ref to LayoutTypeStored
    location: int # ref to LocationStored

    axes: list[str] = Field(frozen=True, default=['default'])
    # order of these elements correspond to position coordinate values
    # can not change after creation or units could not be reliably constructed
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
            # type and location id are visible
            'name': self.redacted_str if self.name is not None else self.name,
            'axes': [self.redacted_str for s in self.axes]
        })
    pass

class Arrangement(ControlledTreeAggregate):

    @property
    def protected(self) -> str | bool:
        for _, layout in self.entries.items():
            if layout.units:
                return "This arrangement is used to define existing units and so cannot be removed"
        return False

    def add_layout(self, layout: LayoutInput, parent_id: int|None, position: tuple|list):
        if parent_id is not None:
            parent_layout = self.get_layout(parent_id)
            if not parent_layout.location == layout.location:
                raise ValueError("All layouts in an arrangement should have the same location")

            if any([
                isinstance(position, (tuple, list)) and not len(position) == len(parent_layout.axes),
                len(parent_layout.axes) != 1
            ]):
                raise ValueError("Position should have same length as the parent layout axes")
            sources = {parent_id: {'position': position}}

        else:
            sources = None

        return super().add_entry(layout, sources)

    def get_layout(self, layout: int):
        return super().get_entry(layout)
