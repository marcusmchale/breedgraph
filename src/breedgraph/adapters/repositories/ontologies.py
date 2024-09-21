"""
Note there may be issues with consistency during edits due to shared nodes across versions.
e.g. if one user changes an attribute it may be lost/written over by another concurrent user
We force a fork on "material" changes so this won't happen when these details are changed,
 but e.g. reference edits may be lost.
 # todo consider how to handle this
"""
import logging
import networkx as nx
from neo4j import AsyncTransaction, Record

from src.breedgraph.adapters.neo4j.cypher import queries, ontology_entries
from src.breedgraph.adapters.repositories.trackable_wrappers import Tracked, TrackedGraph
from src.breedgraph.adapters.repositories.base import BaseRepository

from typing import Set, AsyncGenerator, Protocol

from src.breedgraph.domain.model.ontology import (
    Version, VersionStored, VersionChange,
    Ontology, OntologyEntry, OntologyRelationshipLabel,
)

logger = logging.getLogger(__name__)

class TrackedOntology(Protocol):
    version: Tracked|Version|VersionStored
    graph: TrackedGraph|nx.DiGraph
    licence: int|None
    copyright: int|None
    changed: bool

class Neo4jOntologyRepository(BaseRepository):
    # entry attributes that require forking to a new entry when changed
    material_changes: Set[str] = {
        'name',
        'type'
    }
    def __init__(self, tx: AsyncTransaction):
        super().__init__()
        self.tx = tx

    async def get_latest_version(self) -> VersionStored | None:
        result = await self.tx.run(queries['ontologies']['get_latest_version'])
        record = await result.single()
        if record is not None:
            return VersionStored(**record['version'])

    async def _create(self, version: Version|None = None) -> Ontology:
        """
        This will create a fork of the latest version.

        If no version is specified, a major version change will be applied.
        If no ontology version exists a new empty Ontology will be created.

        """
        latest = await self.get_latest_version()

        if version is None:
            if latest is None:
                version = Version()
            else:
                version = latest
                version.increment(VersionChange.MAJOR)
        else:
            if not version > latest:
                raise ValueError(f"New version numbers must be higher than the latest stored version")

        new_version = await self._create_version(version)

        if latest is None:
            ontology = Ontology(version=new_version)
        else:
            ontology = await self.get()
            ontology.version = new_version

        return ontology

    async def _create_version(self, version: Version) -> VersionStored:
        result = await self.tx.run(
            queries['ontologies']['create_version'],
            major=version.major,
            minor=version.minor,
            patch=version.patch,
            comment=version.comment
        )
        record = await result.single()
        return VersionStored(**record['version'])

    async def _fork_version(
            self,
            ontology: TrackedOntology,
            version_change: VersionChange = VersionChange.PATCH
    ) -> None:
        ontology.version.increment(version_change)
        result = await self.tx.run(
            queries['ontologies']['fork_version'],
            **ontology.version.model_dump()
        )
        record = await result.single()
        ontology.version.id = record.get('version').get('id')

    async def _get(self, version_id: int = None) -> Ontology|None:
        if version_id is None:
            version = await self.get_latest_version()
            if version is None:
                return await self._create()

            version_id = version.id

        result = await self.tx.run(queries['ontologies']['get_ontology'], version_id=version_id)
        record = await result.single()

        if record:
            return Ontology(
                version=VersionStored(**record['version']),
                nodes=[self.record_to_entry(entry) for entry in record['entries']],
                edges=[edge for entry in record['entries'] for edge in entry.get('relates_to', [])]
            )
        else:
            return None

    #async def _set_licence(self, licence_id: int, version_id: int) -> None:
    #    if licence_id is not None:
    #        await self.tx.run(
    #            queries['ontologies']['set_licence'],
    #            licence=licence_id,
    #            version=version_id
    #        )
    #
    #async def _set_copyright(self, copyright_id: int, version_id: int) -> None:
    #    if copyright_id is not None:
    #        await self.tx.run(
    #            queries['ontologies']['set_copyright'],
    #            copyright=copyright_id,
    #            version=version_id
    #        )
    #
    async def _create_entry(self, entry: OntologyEntry, version_id: int) -> OntologyEntry:
        params = entry.model_dump()
        params.pop('id')
        authors = params.pop('authors')
        references = params.pop('references')
        query = ontology_entries.create_ontology_entry(entry.label)
        result = await self.tx.run(
            query=query,
            params=params,
            authors=authors,
            references=references,
            version_id=version_id
        )
        record = await result.single()
        return self.record_to_entry(record['entry'])

    async def _update_entry(self, entry: OntologyEntry):
        params = entry.model_dump()
        entry_id = params.pop('id')
        authors = params.pop('authors')
        references = params.pop('references')
        query = ontology_entries.update_ontology_entry(entry.label)
        await self.tx.run(
            query=query,
            params=params,
            authors=authors,
            references=references,
            entry_id=entry_id
        )

    async def _remove_entry(self, entry: OntologyEntry, version_id: int) -> None:
        await self.tx.run(queries['ontologies']['remove_entry'], entry=entry.id, version=version_id)

    async def _create_edge(self, source_id: int, sink_id: int, label: OntologyRelationshipLabel, rank: int = None):
        query = ontology_entries.create_ontology_edge(label=label)
        await self.tx.run(
            query=query,
            source_id=source_id,
            sink_id=sink_id,
            rank=rank
        )
    async def _update_category_rank(self, source_id: int, sink_id: int, rank: int = None):
        await self.tx.run(
            query=queries['ontologies']['update_category_rank'],
            source_id=source_id,
            sink_id=sink_id,
            rank=rank
        )

    @staticmethod
    def record_to_entry(record: Record) -> OntologyEntry:
        label = [l for l in record['labels'] if l != "OntologyEntry"][0]
        for sc in OntologyEntry.__subclasses__():
            if sc.label == label:
                return sc(**record)

        raise ValueError("Record does not have a recognised OntologyEntry label")

    def _get_all(self) -> AsyncGenerator[Ontology, None]:
        raise NotImplementedError

    async def _remove(self, ontology: Ontology) -> None:
        raise NotImplementedError

    async def _update(self, ontology: TrackedOntology|Ontology):
        if not ontology.changed:
            return

        if any([
            ontology.graph.added_nodes,
            ontology.graph.removed_nodes,
            ontology.graph.changed_nodes and any([
                entry['model'].changed.intersection(self.material_changes) for entry in
                [ontology.graph.nodes[i] for i in ontology.graph.changed_nodes]
            ])
        ]):
            await self._fork_version(ontology, version_change=VersionChange.MINOR)
        else:
            await self._fork_version(ontology, version_change=VersionChange.PATCH)

        for entry_id in ontology.graph.added_nodes:
            _, entry = ontology.get_entry(entry_id)
            if entry_id < 0:
                stored_entry = await self._create_entry(entry, ontology.version.id)
                ontology.graph.replace_with_stored(entry_id, stored_entry)
            else:
                # todo this will be needed to support copying an entry from an earlier version of the ontology
                raise NotImplementedError
        for entry_id in ontology.graph.changed_nodes:
            _, entry = next(ontology.get_entries(entry_id))

            if entry.changed.intersection(self.material_changes):
                stored_entry = await self._create_entry(entry, ontology.version.id)
                ontology.graph.replace_with_stored(entry_id, stored_entry)
            else:
                await self._update_entry(entry)

        for entry_id, entry in ontology.graph.removed_nodes:
            if entry_id >= 0:
                await self._remove_entry(entry, ontology.version.id)

        for edge in ontology.graph.added_edges:
            edge_data = ontology.graph.edges[edge]
            edge_label = edge_data.get('label')
            edge_rank = edge_data.get('label')
            await self._create_edge(source_id=edge[0], sink_id=edge[1], label=edge_label, rank=edge_rank)
        # note do not remove edges or versioning would break.
        # we only allow changing of rank for categories,
        # currently relying on this to be performed sensibly, i.e. to include new categories.
        # todo enforce all of this behaviour in the model
        # todo add tracking of changed_edges to support this update
        #for edge in ontology.graph.changed_edges:
        #    edge_data = ontology.graph.edges[edge]
        #    edge_rank = edge_data.get('label')
        #    await self._update_category_rank(source_id=edge[0], sink_id=edge[1], rank=edge_rank)
