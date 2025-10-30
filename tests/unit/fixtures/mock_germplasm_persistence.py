from typing import Dict, List, Any, Optional, AsyncGenerator
from src.breedgraph.domain.model.germplasm import GermplasmInput, GermplasmStored, GermplasmRelationship, GermplasmOutput
from src.breedgraph.service_layer.persistence.germplasm import GermplasmPersistenceService
import networkx as nx


class MockGermplasmPersistenceService(GermplasmPersistenceService):
    """Mock persistence service for testing germplasm operations."""

    def __init__(self):
        self.entries: Dict[int, GermplasmStored] = {}
        # Use a directed graph to model relationships
        # Nodes are entry IDs, edges represent source -> target relationships
        self.graph = nx.DiGraph()
        self._next_id = 1

    async def _create_entry(self, entry: GermplasmInput) -> GermplasmStored:
        entry_id = self._next_id
        self._next_id += 1

        stored_entry = GermplasmStored(
            id=entry_id,
            name=entry.name,
            description=entry.description,
            synonyms=entry.synonyms,
            authors=entry.authors,
            references=entry.references,
            origin=entry.origin,
            time=entry.time,
            reproduction=entry.reproduction,
            control_methods=entry.control_methods
        )

        self.entries[entry_id] = stored_entry
        # Add node to graph
        self.graph.add_node(entry_id)
        return stored_entry

    async def get_entry(self, entry_id: int) -> Optional[GermplasmStored]:
        return self.entries.get(entry_id)

    async def update_entry(self, entry: GermplasmStored) -> None:
        if entry.id in self.entries:
            self.entries[entry.id] = entry

    async def delete_entry(self, entry_id: int) -> None:
        self.entries.pop(entry_id)

    async def get_root_entries(self) -> AsyncGenerator[GermplasmStored, None]:
        # Root entries are those with no incoming edges (no sources/parents)
        for entry_id in self.entries:
            if self.graph.in_degree(entry_id) == 0:
                yield self.entries[entry_id]

    async def get_entries(
            self,
            entry_ids: List[int] | None = None,
            names: List[str] | None = None,
            as_output: bool = False
    ) -> AsyncGenerator[GermplasmStored|GermplasmOutput, None]:
        if entry_ids:
            for entry_id in entry_ids:
                if entry_id in self.entries:
                    yield self.entries[entry_id]
        if names:
            for entry in self.entries.values():
                if names is None or any(name.casefold() in [n.casefold() for n in entry.names] for name in names):
                    yield entry
        else:
            for entry in self.entries.values():
                yield entry

    async def name_in_use(self, name: str, exclude_id: int | None = None) -> bool:
        for entry_id, entry in self.entries.items():
            if exclude_id and entry_id == exclude_id:
                continue
            if name.casefold() in [n.casefold() for n in entry.names]:
                return True
        return False

    async def entry_exists(self, entry_id: int) -> bool:
        return entry_id in self.entries

    async def entries_exist(self, entry_ids: List[int]) -> Dict[int, bool]:
        return {entry_id: entry_id in self.entries for entry_id in entry_ids}

    async def create_relationships(self, relationships: List[GermplasmRelationship]) -> None:
        for rel in relationships:
            self._create_relationship(rel)

    def _create_relationship(self, relationship) -> None:
        # Add edge from source to target with relationship details
        self.graph.add_edge(relationship.source_id, relationship.sink_id, **relationship.model_dump())

    async def update_relationships(
        self,
        relationships: List[GermplasmRelationship]
    ) -> None:
        for rel in relationships:
            for key, value in rel.model_dump():
                self.graph[rel.source_id][rel.sink_id][key] = value

    async def delete_relationships(
        self,
        relationships: List[GermplasmRelationship]
    ) -> None:
        for rel in relationships:
            self.graph.remove_edge(rel.source_id, rel.sink_id)

    async def get_entry_sources(self, entry_id: int) -> Dict[int, Dict[str, Any]]:
        """Get all source relationships for an entry (incoming edges)."""
        sources = {}
        if entry_id in self.graph:
            for source_id in self.graph.predecessors(entry_id):
                edge_data = self.graph.get_edge_data(source_id, entry_id)
                sources[source_id] = edge_data.copy() if edge_data else {}
        return sources

    async def get_descendant_ids(self, entry_id: int, path_length_limit=None) -> List[int]:
        """
        Get all descendants (entries that have this entry as an ancestor).
        Returns topologically sorted list.
        """
        if entry_id not in self.graph:
            return []

        # Get all nodes reachable from this entry
        if path_length_limit is None:
            descendants = set(nx.descendants(self.graph, entry_id))
        else:
            # For limited path length, use ego_graph
            ego_graph = nx.ego_graph(self.graph, entry_id, radius=path_length_limit, undirected=False)
            descendants = set(ego_graph.nodes()) - {entry_id}

        if not descendants:
            return []

        # Create subgraph of descendants and topologically sort
        descendant_subgraph = self.graph.subgraph(descendants)
        try:
            # Topological sort only works on DAGs
            return list(nx.topological_sort(descendant_subgraph))
        except nx.NetworkXError:
            # If there are cycles, fall back to regular list
            return list(descendants)

    async def get_ancestor_ids(self, entry_id: int, path_length_limit=None) -> List[int]:
        """
        Get all ancestors (entries that are sources to this entry).
        Returns topologically sorted list.
        """
        if entry_id not in self.graph:
            return []

        # Get all nodes that can reach this entry
        if path_length_limit is None:
            ancestors = set(nx.ancestors(self.graph, entry_id))
        else:
            # For limited path length, we need to traverse backwards
            ancestors = set()
            current_level = {entry_id}
            for _ in range(path_length_limit):
                next_level = set()
                for node in current_level:
                    predecessors = set(self.graph.predecessors(node))
                    next_level.update(predecessors)
                    ancestors.update(predecessors)
                if not next_level:
                    break
                current_level = next_level

        if not ancestors:
            return []

        # Create subgraph of ancestors and topologically sort
        ancestor_subgraph = self.graph.subgraph(ancestors)
        try:
            # Topological sort only works on DAGs
            return list(nx.topological_sort(ancestor_subgraph))
        except nx.NetworkXError:
            # If there are cycles, fall back to regular list
            return list(ancestors)

    async def has_path(self, source_id: int, target_id: int) -> bool:
        return target_id in await self.get_descendant_ids(source_id)

    async def get_relationships(self, entry_id: int) -> AsyncGenerator[GermplasmRelationship, None]:
        for edge in self.graph.edges(entry_id, data=True):
            yield GermplasmRelationship(**edge[2])

    async def get_source_relationships(self, entry_id: int) -> AsyncGenerator[GermplasmRelationship, None]:
        for edge in self.graph.in_edges(entry_id, data=True):
            yield GermplasmRelationship(**edge[2])

    async def get_sink_relationships(self, entry_id: int) -> AsyncGenerator[GermplasmRelationship, None]:
        for edge in self.graph.out_edges(entry_id, data=True):
            yield GermplasmRelationship(**edge[2])