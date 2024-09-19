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

 We can then ensure consistency of information across members,
  e.g. genotype may be specified on some units and inferred to others.

Subject is required for all Units, as we need to know at what the unit represents for any analysis.
With pooling, e.g. the unit represents a pool of leaves, the subject would still be "leaf".


"""
from pydantic import BaseModel, field_validator, ValidationInfo

from src.breedgraph.domain.model.base import LabeledModel
from src.breedgraph.domain.model.controls import ControlledModel, ControlledRootedAggregate
from src.breedgraph.domain.model.time_descriptors import PyDT64
from typing import List, ClassVar

class Position(BaseModel):
    location: int
    layout: int | None = None # ref to LayoutStored
    coordinates: list | None = None  # list of axis values should correspond to layout,
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
    synonyms: List[str] = list()
    description: str|None = None

    germplasm: int | None = None  # ref to GermplasmEntryStored
    #  should be constant for units within a tree,
    #  although a Block may include multiple germplasms, each unit should still be singular.
    # Note:
    #   We could handle changing germplasm with temporal references,
    #   This would be used e.g. studying a field that gets planted with different varieties each year,
    #   though such studies seem unlikely so to avoid unnecessary complexity
    #   we currently only support fixed germplasm references.

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
            'germplasm': None,
            'positions': list()
        })

class Block(ControlledRootedAggregate):
    """
        Aggregate for correlated units.
        A single "root" unit is required.
    """
    def add_unit(self, unit: UnitInput, parent_id: int | None = None):
        if parent_id is not None:
            sources = {parent_id: None}
        else:
            sources = None

        return super().add_entry(unit, sources)

    def get_unit(self, unit_id: int):
        return self.graph.nodes[unit_id].get('model')

    def merge_block(self, observation_group: 'Block', parent_id: int):
        """
        A merger requires:
           - a single "Parent" UnitGraph and a selected unit within this.
           - a child UnitGraph to be added as a child to the selected unit in the "Parent" UnitGraph
        :param observation_group: The child graph to merge
        :param parent_id: The node in the current graph to set as the parent.
        """
        if not parent_id in self.graph.nodes:
            raise ValueError("parent_id must correspond to a node in this graph")
        self.graph.update(nodes=observation_group.graph.nodes, edges=observation_group.graph.edges)
        self._add_edge(parent_id, observation_group.get_root_id())
