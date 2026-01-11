from abc import ABC
from dataclasses import dataclass, field, replace
from typing import List, ClassVar, Self, Dict, Any

from src.breedgraph.service_layer.tracking.wrappers import asdict
from src.breedgraph.domain.model.base import LabeledModel, StoredModel, EnumLabeledModel
from src.breedgraph.domain.model.controls import ControlledModel, Controller, ControlledTreeAggregate, Access, \
    ControlledModelLabel


@dataclass
class LayoutBase(ABC):
    label: ClassVar[str] = ControlledModelLabel.LAYOUT

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
class LayoutInput(LayoutBase, EnumLabeledModel):
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
                #location=None, As we can query by location it makes sense to expose this still.
                type=None
            )

@dataclass
class LayoutOutput(LayoutBase, StoredModel, EnumLabeledModel):
    arrangement: int | None = None
    parent: int | None = None
    children: list[int] = field(default_factory=list)
    position: List[str|int|float] = field(default_factory=list)


# Set the generic typing for return of the base model type stored in the graph.
TInput = LayoutInput
TStored = LayoutStored

class Arrangement(ControlledTreeAggregate):
    default_edge_label: ClassVar['str'] = "INCLUDES_LAYOUT"

    @property
    def layouts(self) -> list[LayoutInput | LayoutStored]:
        return list(self.entries.values())

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

    def change_parent(self, layout_id: int, parent_id: int, position: List[str]|None = None):
        super().change_source(layout_id, parent_id, attributes= {'position': position})


    def get_position(self, layout_id: int):
        source_edges = super().get_source_edges(entry_id=layout_id)
        try:
            position = next(iter(source_edges.values())).get('position')
            return position
        except StopIteration:
            return None

    def remove_layout(self, layout_id):
        return super().remove_entry(layout_id)

    def get_layout(self, layout: int) -> LayoutStored:
        layout_model = super().get_entry(layout)
        return layout_model

    def to_output_map(self) -> dict[int, LayoutOutput]:
        return {
            node: LayoutOutput(
                **self.get_layout(node).model_dump(),
                arrangement=self.get_root_id(),
                parent=self.get_parent_id(node),
                children=self.get_children_ids(node),
                position=self.get_position(layout_id=node)
            ) for node in self._graph
        }


