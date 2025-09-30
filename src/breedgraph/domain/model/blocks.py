"""
ObservationUnit is akin to the observation unit from BrAPI but is extended to support samples
 and e.g. split-plot experiments with more complex relationships among observation units

ObservationUnit and Sample in BrAPI are distinguished,
 with ObservationUnit being defined as anything that is being observed,
 and sample being the biological material collected from a plant.
 But then BrAPI allows observations to be recorded against samples highlighting the ambiguity of these terms.

As we sometimes move whole plants in controlled experiments
 and post-processing "events" affect samples
 we can't simply reference a single stable time-point in the lifecycle of any observation unit.
 Instead, we can record e.g. "harvest into liquid N2" as an event for a sample, which is itself a unit like any other.
 In that way the UnitTree aggregates all related units, e.g. the source plant, field etc.

Subject is required for all Units, as we need to know at what the unit represents for any analysis.
With pooling, e.g. the unit represents a pool of leaves, the subject would still be "leaf".

"""
from abc import ABC
from dataclasses import dataclass, field, replace
from numpy import datetime64

from src.breedgraph.service_layer.tracking.wrappers import asdict
from src.breedgraph.domain.model.base import EnumLabeledModel, StoredModel
from src.breedgraph.domain.model.controls import ControlledModel, ControlledRootedAggregate, ReadRelease, Controller, ControlledModelLabel
from src.breedgraph.domain.model.organisations import Access
from typing import List, ClassVar, Generator

@dataclass
class Position:
    location: int | None = None # ref to LocationStored
    layout: int | None = None # ref to LayoutStored
    coordinates: List[int|str|float] | None = None  # list of axis values should correspond to layout,
    start: datetime64|None = None
    end: datetime64|None = None

@dataclass(eq=False)
class UnitBase(ABC):
    """
    Instances of subjects from the ontology
    """
    label: ClassVar[ControlledModelLabel] = ControlledModelLabel.UNIT

    subject: int = None  # ref to SubjectTypeStored

    name: str|None = None
    description: str|None = None

    positions: List[Position] = field(default_factory = list)

    def model_dump(self):
        return asdict(self)

@dataclass
class UnitInput(UnitBase, EnumLabeledModel):
    pass

@dataclass(eq=False)
class UnitStored(UnitBase, ControlledModel):

    def redacted(
            self,
            controller: Controller,
            user_id=None,
            read_teams=None
    ):
        if controller.has_access(Access.READ, user_id, read_teams):
            return self
        else:
            return replace(
                self,
                name=self.name and self.redacted_str,
                description=self.description and self.redacted_str,
                positions=list()
            )

@dataclass(eq=False)
class UnitOutput(UnitBase, EnumLabeledModel, StoredModel):
    parents: list[int] = field(default_factory=list)
    children: list[int] = field(default_factory=list)

TInput = UnitInput
TStored = UnitStored
class Block(ControlledRootedAggregate):
    """
        Aggregate for correlated units.
        A single "root" unit is required.
    """
    default_edge_label: ClassVar['str'] = "INCLUDES_UNIT"

    def add_unit(self, unit: UnitInput, parents: List[int]|None = None) -> int:
        if parents is not None:
            sources = {parent: None for parent in parents}
        else:
            sources = None

        return super().add_entry(unit, sources)

    def remove_unit(self, unit_id: int):
        raise NotImplementedError

    def update_unit(self, unit_id: int, unit: UnitStored):
        raise NotImplementedError

    def get_unit(self, unit_id: int):
        return self._graph.nodes[unit_id].get('model')

    def set_child(self, source_id: int, sink_id: int):
        self._add_edge(source_id, sink_id)

    def merge_block(self, block: 'Block', parents: List[int]):
        """
        A merger requires:
           - a single "Parent" UnitGraph and a selected unit within this.
           - a child UnitGraph to be added as a child to the selected unit in the "Parent" UnitGraph
        :param block: The child graph to merge
        :param parents: The nodes in the current graph to set as the parents for the incoming block.
        """
        for parent_id in parents:
            if not parent_id in self._graph.nodes:
                raise ValueError("parent_id must correspond to a node in this graph")
            self._graph.update(nodes=block._graph.nodes(data=True), edges=block._graph.edges)
            self._add_edge(parent_id, block.get_root_id())

    def to_output_map(self) -> dict[int, UnitOutput]:
        return {node: UnitOutput(
            **self.get_unit(node).model_dump(),
            parents=self.get_parent_ids(node),
            children=self.get_children_ids(node),
        ) for node in self._graph}

    def yield_unit_ids_by_subject(self, subject_id: int) -> Generator[int, None, None]:
        for unit_id, unit in self.entries.items():
            if unit.subject_id == subject_id:
                yield unit_id