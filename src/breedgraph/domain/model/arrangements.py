from abc import ABC
from dataclasses import dataclass, field, replace
from typing import List, ClassVar, Self

from breedgraph.domain.model.base import StoredModel, EnumLabeledModel
from breedgraph.domain.model.controls import ControlledModel, Controller, ControlledTreeAggregate, ControlledModelLabel, Access

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

    def __post_init__(self):
        if len(set(self.axes)) != len(self.axes):
            raise ValueError("Axis names should be unique within a layout")

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
    """A hierarchical collection of layouts defining a coordinate context.

    An arrangement provides the root context for a hierarchy of layouts.
    Parent-child relationships establish scope and context, but do not
    necessarily imply that a child layout refines its parent.

    Layouts in different branches may define independent coordinate spaces
    and may reuse axis names. An axis name must not occur more than once
    along any root-to-leaf path within the arrangement.

    Relationships between coordinate spaces, including composition and
    projection through shared axes, are derived when resolving positions
    rather than explicitly represented by the arrangement.
    """

    default_edge_label: ClassVar['str'] = "INCLUDES_LAYOUT"

    @property
    def layouts(self) -> list[LayoutInput | LayoutStored]:
        return list(self.entries.values())

    def _validate_names(
            self,
            layout: LayoutInput | LayoutStored,
            parent_id: int | None,
    ):
        if parent_id is None:
            layouts = self.layouts
        else:
            parent_layout = self.get_layout(parent_id)
            if parent_layout is None:
                raise ValueError(f"Parent layout {parent_id} does not exist")

            layouts = [self.get_entry(i) for i in self.get_ancestors(parent_id)] + [parent_layout]

        existing_axis_names = [name for l in layouts for name in l.axes ]
        overlap = set(existing_axis_names).intersection(set(layout.axes))
        if overlap:
            raise ValueError(f"Axis names { overlap } already in use within this branch of the arrangement")

    def add_layout(self, layout: LayoutInput, parent_id: int|None, position: List[str]|None):
        self._validate_names(layout, parent_id)

        if parent_id is None:
            # insert layout as new root for the arrangement
            sources = None

        else:
            parent_layout = self.get_layout(parent_id)

            if layout.location is not None:
                if not parent_layout.location == layout.location:
                    raise ValueError("All layouts in an arrangement should have the same location")

            if position is None:
                raise ValueError("Position is required for child layouts")

            if not len(position) == len(parent_layout.axes):
                raise ValueError("Position should have same length as the parent layout axes")

            sources = {parent_id: {'position': position}}

        return super().add_entry(layout, sources)

    def change_parent(self, layout_id: int, parent_id: int, position: List[str]|None = None):
        layout = self.get_layout(layout_id)
        self._validate_names(layout, parent_id)

        if position is None:
            raise ValueError("Position is required within parent layout")

        parent_layout = self.get_layout(parent_id)
        if not len(position) == len(parent_layout.axes):
            raise ValueError("Position should have same length as the parent layout axes")

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

    def yield_layouts_by_type(self, type_id: int):
        for e in self.entries.values():
            if e.type == type_id:
                yield e

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

    def get_location(self, layout_id) -> int | None:
        for lid in [layout_id, *reversed(self.get_ancestors(layout_id))]:
            location = self.get_layout(lid).location
            if location is not None:
                return location
        return None



