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
from pydantic import BaseModel, field_validator, ValidationInfo

from src.breedgraph.domain.model.base import LabeledModel
from src.breedgraph.domain.model.controls import ControlledModel, ControlledRootedAggregate, ReadRelease
from src.breedgraph.domain.model.time_descriptors import PyDT64
from typing import List, ClassVar, Generator

class Position(BaseModel):
    location: int
    layout: int | None = None # ref to LayoutStored
    coordinates: List[int|str|float] | None = None  # list of axis values should correspond to layout,
    start: PyDT64
    end: PyDT64|None = None

class Unit(LabeledModel):
    """
    Instances of subjects from the ontology
    """
    label: ClassVar[str] = 'Unit'
    plural: ClassVar[str] = 'Units'

    subject: int  # ref to SubjectTypeStored

    name: str|None = None
    synonyms: List[str]|None = list()
    description: str|None = None

    positions: List[Position] = list()

    @property
    def names(self):
        names = [self.name] + self.synonyms
        return [n for n in names if n is not None]

class UnitInput(Unit):
    pass

class UnitStored(Unit, ControlledModel):

    def redacted(self):
        return self.model_copy(deep=True, update={
            # subject is still visible
            'name': self.redacted_str if self.name is not None else None,
            'synonyms': [self.redacted_str] if self.synonyms else list(),
            'description': self.redacted_str if self.description is not None else None,
            'positions': list()
        })

class UnitOutput(UnitStored):
    parents: list[int]
    children: list[int]
    release: ReadRelease

class Block(ControlledRootedAggregate):
    """
        Aggregate for correlated units.
        A single "root" unit is required.
    """
    def add_unit(self, unit: UnitInput, parents: List[int]|None = None) -> int:
        if parents is not None:
            sources = {parent: None for parent in parents}
        else:
            sources = None

        return super().add_entry(unit, sources)

    def get_unit(self, unit_id: int):
        return self.graph.nodes[unit_id].get('model')

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
            if not parent_id in self.graph.nodes:
                raise ValueError("parent_id must correspond to a node in this graph")
            self.graph.update(nodes=block.graph.nodes(data=True), edges=block.graph.edges)
            self._add_edge(parent_id, block.get_root_id())

    def to_output_map(self) -> dict[int, UnitOutput]:
        return {node: UnitOutput(
            **self.get_unit(node).model_dump(),
            parents=self.get_parent_ids(node),
            children=self.get_children_ids(node),
            release=self.get_unit(node).controller.release
        ) for node in self.graph}

    def yield_unit_ids_by_subject(self, subject_id: int) -> Generator[int, None, None]:
        for unit_id, unit in self.entries.items():
            if unit.subject == subject_id:
                yield unit_id