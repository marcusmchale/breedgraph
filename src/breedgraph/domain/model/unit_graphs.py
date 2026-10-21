"""
ObservationUnit is akin to the observation unit from BrAPI but is extended to include samples.

The justification for this merger of terms:
  - There is an ambiguity in the definitions of these concepts.
    In BrAPI, ObservationUnit is defined as anything that is being observed,
    while sample is the biological material collected from a plant
    However, BrAPI allows observations to be recorded against samples.

  - The observation unit in BrAPI is suitable only for the smallest unit of replication in a study.
    This fails to capture stratification of data from different units of replication.
    For example, we may collect observations from the field, plot( or nested plots) the plant or even tissue.
    The relationship among these entities is central to any analysis that attempts to aggregate such data.
  - Note:
    BrAPI started to implement support for ObservationUnitLevelRelationships
    as part of the ObservationUnitPosition in v2.1.
    This system provides undirected links to other ObservationUnits.
    It relies on the hierarchy of established observation units.
    One weakness is that the position lacks time data.


In BreedGraph, the "unit graph" concept aggregates all related units, e.g. the source plant, field etc. into a rooted graph.
Subject (an ontology reference) is required for all Units, to capture what each unit represents.

To simplify modeling the relationships among experimental units,
we represent the primary location that a plant is grown throughout the expected period of observation
as the root unit for a unit graph of related plants. With this, we can simplify record collection for shared histories
as long as we ensure we have a start and end time for each child unit within each parent unit.

This means we shouldn't handle other transient groups as unit graphs. For example, these should not be registered as a unit graph:
  - A batch of trees from the nursery that is split over many fields.
  - A collection of samples from multiple fields that are sent together for analysis.

Unit graphs should not ordinarily be split, or information stored on parent nodes that is relevant to child nodes will be lost.
 They can however be merged without issue.
 An exception to the restriction on splitting unit graphs is needed to handle erroneous unit graph creation.
 As such, edits should be handled carefully in front end implementations.
 Another situation could be temporary unit graph creation, then merger


"""
from abc import ABC
from dataclasses import dataclass, field, replace

import networkx as nx
from numpy import datetime64
from breedgraph.domain.model.time_descriptors import same_time, local_datetime64

from breedgraph.custom_exceptions import IllegalOperationError
from breedgraph.service_layer.tracking.wrappers import asdict
from breedgraph.domain.model.base import EnumLabeledModel, StoredModel
from breedgraph.domain.model.controls import ControlledModel, ControlledRootedAggregate, Controller, ControlledModelLabel, Access

from typing import List, ClassVar, Generator

@dataclass
class Position:
    location_id: int | None = None # ref to LocationStored
    layout_id: int | None = None # ref to LayoutStored
    coordinates: List[int|str|float] | None = None  # list of axis values should correspond to layout,
    start: datetime64|None = None
    end: datetime64|None = None


def same_position(position: Position, other: Position) -> bool:
    """
    Whether two positions are the same value as entered: positions have no identity, so a position is found by its
    value. Times compare with their precision (numpy counts 2021-05 and 2021-05-01 as equal), and coordinates as the
    strings the API takes them in, none and an empty list alike.
    """
    def coordinates(p: Position):
        return [str(c) for c in p.coordinates or []]

    def time(t):
        return None if t is None else local_datetime64(t)

    return (
        position.location_id == other.location_id
        and position.layout_id == other.layout_id
        and coordinates(position) == coordinates(other)
        and same_time(time(position.start), time(other.start))
        and same_time(time(position.end), time(other.end))
    )

@dataclass(eq=False)
class UnitBase(ABC):
    """
    Instances of subjects from the ontology
    """
    label: ClassVar[ControlledModelLabel] = ControlledModelLabel.UNIT

    subject: int|None = None  # ref to SubjectTypeStored
    germplasm: int|None = None  # ref to GermplasmStored

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
                subject=None,
                germplasm=None,
                positions=list()
            )

@dataclass(eq=False)
class UnitOutput(UnitBase, EnumLabeledModel, StoredModel):
    parents: list[int] = field(default_factory=list)
    children: list[int] = field(default_factory=list)


@dataclass
class UnitArrival:
    """
    Units that came to a location together from elsewhere in their unit graphs, e.g. samples sent to a lab: known by the
    location and the start of their positions there, as entered (None for positions without one)
    """
    location_id: int
    start: datetime64 | None
    unit_count: int = 0
    root_ids: List[int] = field(default_factory=list)


def arrival_key(location_id: int, start: datetime64 | None) -> tuple[int, str | None]:
    """An arrival's key: its location and its start as entered, as text"""
    return location_id, None if start is None else str(start)


TInput = UnitInput
TStored = UnitStored
class UnitGraph(ControlledRootedAggregate):
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
        self.remove_entry(unit_id)

    def has_unit(self, unit_id: int):
        return self._graph.has_node(unit_id)

    def get_unit(self, unit_id: int):
        return self._graph.nodes[unit_id].get('model')

    def set_child(self, source_id: int, sink_id: int):
        self._add_edge(source_id, sink_id)

    def change_parents(self, unit_id, new_parent_ids):
        if not new_parent_ids and self.get_parent_ids(unit_id):
            raise IllegalOperationError(
                "A unit with parents keeps at least one: to make it the root of a unit graph, split the unit graph"
            )
        self._change_sources(unit_id, set(new_parent_ids))

    def change_children(self, unit_id, new_child_ids):
        """
        Make new_child_ids the unit's children, within this unit graph. A child the unit alone holds can't be let go
        here, as it would be left without parents: splitting the unit graph makes it a root instead.
        """
        current_child_ids = self.get_children_ids(unit_id)
        to_remove = set(current_child_ids) - set(new_child_ids)
        to_add = set(new_child_ids) - set(current_child_ids)
        for child_id in to_remove:
            current_parents = self.get_parent_ids(child_id)
            new_parents = set(current_parents) - {unit_id}
            self.change_parents(child_id, new_parents)
        for child_id in to_add:
            if not self.has_unit(child_id):
                raise ValueError(f"Child {child_id} is not in this unit graph: merge its unit graph instead")
            self.set_child(source_id = unit_id, sink_id=child_id)


    def merge_unit_graph(self, unit_graph: 'UnitGraph', parents: List[int]):
        """
        A merger requires:
           - a single "Parent" UnitGraph and a selected unit within this.
           - a child UnitGraph to be added as a child to the selected unit in the "Parent" UnitGraph
        :param unit_graph: The child graph to merge
        :param parents: The nodes in the current graph to set as the parents for the incoming unit graph.
        """
        for parent_id in parents:
            if not parent_id in self._graph.nodes:
                raise ValueError("parent_id must correspond to a node in this graph")
            self._graph.update(nodes=unit_graph._graph.nodes(data=True), edges=unit_graph._graph.edges)
            self._add_edge(parent_id, unit_graph.get_root_id())

    def to_output_map(self) -> dict[int, UnitOutput]:
        return {node: UnitOutput(
            **self.get_unit(node).model_dump(),
            parents=self.get_parent_ids(node),
            children=self.get_children_ids(node),
        ) for node in self._graph}

    def yield_unit_ids_by_subject(self, subject_id: int) -> Generator[int, None, None]:
        for unit_id, unit in self.entries.items():
            if unit.subject == subject_id:
                yield unit_id
