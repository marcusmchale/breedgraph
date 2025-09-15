from abc import ABC
from typing import Generic, ClassVar, List, Tuple, Set, Dict, TypeVar

import networkx as nx

from src.breedgraph.custom_exceptions import IllegalOperationError, NoResultFoundError
from src.breedgraph.domain.model.base import Aggregate, logger

TInput = TypeVar('TInput')
TStored = TypeVar('TStored')

class DiGraphAggregate(Aggregate, Generic[TInput, TStored], ABC):
    default_edge_label: ClassVar[str]

    def __init__(self, nodes: List[TInput|TStored] = None, edges: List[Tuple[int, int, dict|None]]|None = None, **kwargs):
        self._temp_id: int = 0  # each instance starts with temp_id 0, these decrement with each access request
        # when committed by repository, temporary IDs should all be replaced and this value reset to 0
        self._graph = nx.DiGraph()
        super().__init__()
        if nodes is not None:
            self._add_nodes(nodes)
        if edges is not None:
            self._add_edges(edges)

    @property
    def temp_id(self) -> int:
        self._temp_id -= 1
        return self._temp_id

    @property
    def root(self) -> TInput|TStored|None:
        return None

    @property
    def size(self):
        return self._graph.number_of_nodes()

    @property
    def protected(self) -> str|None:
        if self._graph.number_of_nodes() > 1:
            return "Cannot delete DiGraph with more than one node"
        else:
            return None

    @property
    def entries(self) -> Dict[int, TInput|TStored]:
        return nx.get_node_attributes(self._graph, 'model')

    def get_entry(self, entry: int | str) -> TInput|TStored:
        """ Search by integer ID or by name """
        if isinstance(entry, int):
            return self._graph.nodes[entry].get('model')
        elif isinstance(entry, str):
            for e in self.entries.values():
                if hasattr(e, 'name'):
                    if entry.casefold() == e.name.casefold():
                        return e
                elif hasattr(e, 'names'):
                    if entry.casefold() in [n.casefold() for n in e.names]:
                        return e
        raise NoResultFoundError(f"Entry {entry} was not found")

    def _add_node(self, model: TInput) -> int:
        """
        Add a node to the graph
        :param model: Model to be added to the graph as a node
        :return: Returns node ID, useful if adding a model that doesn't have its own ID
        """
        if hasattr(model, 'id'):
            node_id = model.id or self.temp_id
        else:
            node_id = self.temp_id

        if node_id in self._graph.nodes:
            raise ValueError("Duplicate node")

        self._graph.add_node(node_id, model=model, label=model.label)
        return node_id

    def _add_nodes(self, nodes: List[TInput]) -> List[int]:
        return [self._add_node(node) for node in nodes]

    def _add_edge(self, source_id: int, sink_id: int, **kwargs):
        # may use kwargs to store additional properties on an edge
        if not source_id in self._graph:
            raise ValueError(f"Source node not found: {source_id}")
        if not sink_id in self._graph:
            raise ValueError(f"Sink node not found: {sink_id}")
        if sink_id == source_id:
            raise IllegalOperationError(f"Self-loop references are not supported")
        if sink_id in self.get_ancestors(source_id):
            raise IllegalOperationError(f"This edge would create a cycle which are not supported")
        self._graph.add_edge(source_id, sink_id, **kwargs)


    def _add_edges(self, edges: List[Tuple[int, int, dict]]):
        for edge in edges:
            self._add_edge(edge[0], edge[1], **edge[2] if edge[2] else {})

    def _remove_nodes(self, node_ids: List[int] | int):
        if isinstance(node_ids, int):
            node_ids = [node_ids]
        for node, degree in self._graph.out_degree(node_ids):
            if degree > 0:
                raise IllegalOperationError(f"Cannot remove a node with children: {node}")

        self._graph.remove_nodes_from(node_ids)

    def get_nodes(self, node_ids: List[int]|None = None):
        if node_ids is None:
            return self._graph.nodes

        return [self._graph.nodes[node_id] for node_id in node_ids]

    def get_descendants(self, node_id):
        """Returns descendants sorted by distance (closest first)"""
        if node_id not in self._graph:
            return []

        # Get all descendants
        descendants = nx.descendants(self._graph, node_id)

        if not descendants:
            return []

        # Calculate distances only for descendants and sort
        descendant_distances = []

        for descendant_id in descendants:
            try:
                distance = nx.shortest_path_length(self._graph, node_id, descendant_id)
                descendant_distances.append((distance, descendant_id))
            except nx.NetworkXNoPath:
                # This shouldn't happen for true descendants, but just in case
                continue

        return [descendant_id for _, descendant_id in sorted(descendant_distances)]

    def get_ancestors(self, node_id):
        """Returns ancestors sorted by distance (closest first)"""
        if node_id not in self._graph:
            return []

        # Get all ancestors
        ancestors = nx.ancestors(self._graph, node_id)

        if not ancestors:
            return []

        # Calculate distances only for ancestors and sort
        reversed_graph = self._graph.reverse(copy=False)
        ancestor_distances = []

        for ancestor_id in ancestors:
            try:
                distance = nx.shortest_path_length(reversed_graph, node_id, ancestor_id)
                ancestor_distances.append((distance, ancestor_id))
            except nx.NetworkXNoPath:
                # This shouldn't happen for true ancestors, but just in case
                continue

        return [ancestor_id for _, ancestor_id in sorted(ancestor_distances)]

    def _change_sources(self, node_id: int, sources: Set[int]):
        if node_id in sources:
            raise ValueError("Node is in sources, self-loops are not supported")
        if set(sources).intersection(self.get_descendants(node_id)):
            raise IllegalOperationError("A supplied source is a child, cycles are not supported")

        self._graph.remove_edges_from(list(self._graph.in_edges(node_id)))
        self._graph.add_edges_from([(source_id, node_id) for source_id in sources])

    @staticmethod
    def remove_node_and_reconnect(graph: nx.DiGraph, node_id: int, label: str=None):
        for in_src, _ in graph.in_edges(node_id):
            for _, out_dst in graph.out_edges(node_id):
                graph.add_edge(in_src, out_dst, label=label)
        graph.remove_node(node_id)


class RootedAggregate(DiGraphAggregate, ABC):
    """ An aggregate a single source node is an ancestor of all nodes """


    def __init__(self, nodes=None, edges=None, **kwargs):
        super().__init__(nodes, edges, **kwargs)

        if len(self._graph) > 0:
            if not nx.is_weakly_connected(self._graph):
                raise ValueError("DiGraph is not weakly connected")

            root_count = 0
            for node, degree in self._graph.in_degree():
                if degree == 0:
                    root_count += 1
            if root_count != 1:
                raise ValueError("RootedAggregate must have a singular root")

    def get_root_id(self) -> int:
        return next(nx.topological_sort(self._graph))

    @property
    def root(self) -> TInput|TStored|None:
        try:
            root_id = self.get_root_id()
        except StopIteration:
            return None
        return self._graph.nodes[root_id].get('model')

    @property
    def protected(self) -> str | None:
        if self.size > 1:
            return "Cannot delete a rooted aggregate with more than one entry"
        else:
            return None

    def insert_root(self, entry: TInput, details: dict = None) -> int:
        """
        Allows inserting a new root node that will become the source for the current root node
        kwargs are added to the edge between these
        """
        root_id = self.get_root_id()
        entry_id = self._add_node(entry)
        self._add_edge(entry_id, root_id, **details if details else {})
        return entry_id

    def add_entry(self, entry: TInput, sources: Dict[int, dict] = None) -> int:
        """Returns the temporary ID for the entry in the graph"""
        if self._graph and not sources:
            logger.debug("Replacing the root node")
            return self.insert_root(entry)

        entry_id = self._add_node(entry)
        if sources:
            for source, details in sources.items():
                self._add_edge(source, entry_id, **details if details else {})

        return entry_id

    def remove_entry(self, entry_id: int):
        """Remove an entry matching the ID from the graph"""
        if self.get_sinks(entry_id):
            raise IllegalOperationError("Cannot remove a node with sinks")

        self._graph.remove_node(entry_id)

    def get_sources(self, entry_id: int) -> Dict[int, TInput|TStored]:
        return {e[0] : self.get_entry(e[1]) for e in self._graph.in_edges(entry_id)}

    def get_sinks(self, entry_id: int) -> Dict[int, TInput|TStored]:
        return {e[1] : self.get_entry(e[1]) for e in self._graph.out_edges(entry_id)}

    def get_source_edges(self, entry_id: int) -> Dict[int, dict]:
        return {e[0]: e[2] for e in self._graph.in_edges(entry_id, data=True)}

    def get_sink_edges(self, entry_id: int) -> Dict[int, dict]:
        return {e[0]: e[2] for e in self._graph.out_edges(entry_id, data=True)}

    def get_parent_ids(self, node_id: int) -> List[int]:
        return [edge[0] for edge in self._graph.in_edges(node_id)]

    def get_children_ids(self, node_id: int) -> List[int]:
        return [edge[1] for edge in self._graph.out_edges(node_id)]


class TreeAggregate(RootedAggregate, ABC):
    """An aggregate where nodes in the graph each have a single source"""

    def __init__(self, nodes=None, edges=None, **kwargs):
        super().__init__(nodes, edges, **kwargs)

        if len(self._graph) > 0:
            for node, degree in self._graph.in_degree():
                if degree > 1:
                    raise ValueError("TreeAggregate nodes must have a single source")

    def change_source(self, node_id: int, parent_id: int):
        self._change_sources(node_id, {parent_id})

    def get_parent_id(self, node_id: int) -> int | None:
        in_edges = list(self._graph.in_edges(node_id))
        if in_edges:
            return in_edges[0][0]
        else:
            return None
