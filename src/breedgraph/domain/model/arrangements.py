from abc import ABC
from dataclasses import dataclass, field, replace
from typing import List, ClassVar, Self, Dict, Any

from src.breedgraph.service_layer.tracking.wrappers import asdict
from src.breedgraph.domain.model.base import LabeledModel
from src.breedgraph.domain.model.controls import ControlledModel, Controller, ControlledTreeAggregate, Access

@dataclass
class LayoutBase(ABC):
    label: ClassVar[str] = 'Layout'
    plural: ClassVar[str] = 'Layouts'

    name: str | None = None
    type: int|None = None # ref to LayoutTypeStored
    location: int|None = None # ref to LocationStored

    # names for the axes, types are defined in the LayoutType, should be in the same order as LayoutType
    # should not change after creation or units positions could not be reliably constructed
    axes: list[str] = field(default_factory=list)

    @property
    def names(self):
        return [self.name]

    def __hash__(self):
        return hash(self.name)

@dataclass
class LayoutInput(LayoutBase, LabeledModel):
    pass

@dataclass
class LayoutStored(LayoutBase, ControlledModel):

    def redacted(
            self,
            controller: Controller,
            user_id = None,
            read_teams = None
    ) -> Self:
        if controller.has_access(Access.READ, user_id, read_teams):
            return self
        else:
            return replace(
                self,
                name=self.name and self.redacted_str,  # replace name if "truthy"
                axes=list(),
                location=None,
                type=None
            )

@dataclass
class LayoutOutput(LayoutBase, LabeledModel):
    parent: int | None = None
    children: list[int] = field(default_factory=list)


# Set the generic typing for return of the base model type stored in the graph.
TInput = LayoutInput
TStored = LayoutStored
class Arrangement(ControlledTreeAggregate):
    default_edge_label: ClassVar['str'] = "INCLUDES_LAYOUT"

    def add_layout(self, layout: LayoutInput, parent_id: int|None, position: List[str]|None):
        if parent_id is None:
            # insert layout as new root for the arrangement
            sources = None
        else:
            parent_layout: LayoutBase = self.get_layout(parent_id)
            if layout.location is not None:
                if not parent_layout.location == layout.location:
                    raise ValueError("All layouts in an arrangement should have the same location")

            if not len(position) == len(parent_layout.axes):
                raise ValueError("Position should have same length as the parent layout axes")

            sources = {parent_id: {'position': position}}

        return super().add_entry(layout, sources)

    def get_layout(self, layout: int) -> LayoutStored:
        layout_model = super().get_entry(layout)
        return layout_model

    def to_output_map(self) -> dict[int, LayoutOutput]:
        return {
            node: LayoutOutput(
                **self.get_layout(node).model_dump(),
                parent=self.get_parent_id(node),
                children=self.get_children_ids(node),
            ) for node in self._graph
        }
