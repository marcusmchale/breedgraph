from pydantic import BaseModel, Field, computed_field, field_validator, model_validator

from abc import ABC, abstractmethod
from typing import List, Dict, ClassVar, Any, Set, Tuple, TypedDict
import networkx as nx

from typing import TYPE_CHECKING

from src.breedgraph.custom_exceptions import IllegalOperationError
from src.breedgraph.domain.model.graph import PyDiGraph
from src.breedgraph.domain.events.accounts import Event

class LabeledModel(BaseModel):
    label: ClassVar[str] = None
    plural: ClassVar[str] = None

class StoredEntity(ABC, LabeledModel):

    id: int = Field(frozen=True)

    def __hash__(self):
        return hash(self.id)

class Aggregate(ABC, BaseModel):
    events: List[Event] = list()

    @property
    @abstractmethod
    def root(self) -> StoredEntity:
        raise NotImplementedError

    @property
    @abstractmethod
    def protected(self) -> str|None:
        # Return a string describing why this aggregate is protected
        # or None/empty string if safe to delete
        raise NotImplementedError

    def __hash__(self) -> int:
        return hash(self.root.id)


class DiGraphAggregate(Aggregate):
    graph: PyDiGraph = Field(default_factory=lambda: nx.DiGraph())
    _temp_id: int = 0  # each instance starts with temp_id 0, these decrement with each access request
    # when committed by repository, temporary IDs should all be replaced and this value reset to 0

    def __init__(self, nodes: List[LabeledModel] = None, edges: List[Tuple[int, int, dict]]|None = None, **kwargs):
        super().__init__(**kwargs)
        if nodes is not None:
            self._add_nodes(nodes)
        if edges is not None:
            self._add_edges(edges)

    @property
    def temp_id(self) -> int:
        self._temp_id -= 1
        return self._temp_id

    @abstractmethod
    def root(self) -> StoredEntity:
        raise NotImplementedError

    @property
    def size(self):
        return self.graph.number_of_nodes()

    @property
    def protected(self) -> str|None:
        if self.graph.number_of_nodes() > 1:
            return "Cannot delete DiGraph with more than one node"

    def _add_node(self, model: BaseModel) -> int:
        """
        Add a node to the graph 
        :param model: BaseModel to be added to the graph as a node
        :return: Returns node ID, useful if adding a model that doesn't have its own ID
        """        
        if hasattr(model, 'id') and model.id is not None:
            node_id = model.id
        else:
            node_id = self.temp_id

        if node_id in self.graph.nodes:
            raise ValueError("Duplicate node")
        self.graph.add_node(node_id, model=model, label=model.label)
        return node_id

    def _add_nodes(self, nodes: List[BaseModel]) -> List[int]:
        return [self._add_node(node) for node in nodes]

    def _add_edge(self, source_id: int, target_id: int, label: str, **kwargs):
        # use kwargs to store additional properties on an edge
        # label is equivalent to "type" in neo4j
        if not source_id in self.graph:
            raise ValueError(f"Source node not found: {source_id}")
        if not target_id in self.graph:
            raise ValueError(f"Target node not found: {target_id}")
        if target_id == source_id:
            raise IllegalOperationError(f"Self-loop references are not supported")
        if target_id in self.get_ancestors(source_id):
            raise IllegalOperationError(f"This edge would create a cycle which are not supported")

        self.graph.add_edge(source_id, target_id, label=label, **kwargs)

    def _add_edges(self, edges: List[Tuple[int, int, dict]]):
        for edge in edges:
            self._add_edge(edge[0], edge[1], **edge[2])

    def _remove_nodes(self, node_ids: List[int] | int):
        if isinstance(node_ids, int):
            node_ids = [node_ids]
        for node, degree in self.graph.out_degree(node_ids):
            if degree > 0:
                raise IllegalOperationError(f"Cannot remove a node with children: {node}")

        self.graph.remove_nodes_from(node_ids)

    def get_nodes(self, node_ids=None, ):
        if node_ids is None:
            return self.graph.nodes

        return self.graph.nodes[node_ids]

    def get_descendants(self, node_id):
        return nx.descendants(self.graph, node_id)

    def get_ancestors(self, node_id):
        return nx.ancestors(self.graph, node_id)

    def _change_sources(self, node_id: int, sources: Set[int]):
        if node_id in sources:
            raise ValueError("Node is in sources, self-loops are not supported")
        if set(sources).intersection(self.get_descendants(node_id)):
            raise IllegalOperationError("A supplied source is a child, cycles are not supported")

        self.graph.remove_edges_from(list(self.graph.in_edges(node_id)))
        self.graph.add_edges_from([(source_id, node_id) for source_id in sources])

class RootedAggregate(DiGraphAggregate):
    """ An aggregate a single source node is an ancestor of all nodes """

    def __init__(self, nodes=None, edges=None, **kwargs):
        super().__init__(nodes, edges, **kwargs)

        if len(self.graph) > 0:
            if not nx.is_weakly_connected(self.graph):
                raise ValueError("DiGraph is not weakly connected")

            root_count = 0
            for node, degree in self.graph.in_degree():
                if degree == 0:
                    root_count += 1
            if root_count != 1:
                raise ValueError("RootedAggregate must have a singular root")

    def get_root_id(self) -> int:
        return next(nx.topological_sort(self.graph))

    @computed_field
    def root(self) -> StoredEntity | None:
        try:
            root_id = self.get_root_id()
        except StopIteration:
            return None

        return self.graph.nodes[root_id].get('model')

    @property
    def protected(self) -> str | None:
        if self.size > 1:
            return "Cannot delete a rooted aggregate with more than one entry"

    @computed_field
    def entries(self) -> List[BaseModel]:
        return nx.get_node_attributes(self.graph, 'model')

    def insert_root(self, entry: BaseModel, label: str, **kwargs) -> int:
        """Allows inserting a new root node that will become the source for the current root node"""
        root_id = self.get_root_id()
        entry_id = self._add_node(entry)
        self._add_edge(entry_id, root_id, label=label, **kwargs)
        return entry_id

    def add_entry(self, entry: BaseModel, sources: List[Tuple[int, Dict|BaseModel]]) -> int:
        """Returns the temporary ID for the germplasm entered into the graph"""
        if self.graph and not sources:
            raise ValueError("Multiple root nodes are not supported")
        for source in sources:
            if source[0] not in self.graph.nodes:
                raise ValueError(f"Source not found: {source}")
        entry_id = self._add_node(entry)
        for source, details in sources:
            self._add_edge(source, entry_id, **dict(details))
        return entry_id

    def get_entry(self, entry: int | str) -> BaseModel:
        """ Search by integer ID or by name """
        if isinstance(entry, int):
            return self.graph.nodes[entry].get('model')
        elif isinstance(entry, str):
            for e in self.entries.values():
                if entry.casefold() in [n.casefold() for n in e.names]:
                    return e


class TreeAggregate(RootedAggregate):
    """An aggregate where nodes in the graph each have a single source"""

    def __init__(self, nodes=None, edges=None, **kwargs):
        super().__init__(nodes, edges, **kwargs)

        if len(self.graph) > 0:
            for node, degree in self.graph.in_degree():
                if degree > 1:
                    raise ValueError("TreeAggregate nodes must have a single source")

    def change_source(self, node_id: int, parent_id: int):
        self._change_sources(node_id, {parent_id})
