"""
Note there may be issues with consistency during edits due to shared nodes across versions.
e.g. if one user changes an attribute it may be lost/written over by another concurrent user
We force a fork on "material" changes so this won't happen when these details are changed,
 but e.g. reference edits may be lost.
 # todo consider how to handle this
"""
import logging
import re
import networkx as nx
from enum import IntEnum
from neo4j import AsyncTransaction, Record

from src.breedgraph.adapters.neo4j.cypher import queries, ontology_entries
from src.breedgraph.adapters.repositories.trackable_wrappers import Tracked, TrackedDict, TrackedGraph
from src.breedgraph.adapters.repositories.base import BaseRepository

from typing import Set, AsyncGenerator, Protocol

from src.breedgraph.domain.model.ontology import (
    Ontology, Version, VersionStored,
    OntologyEntry
)

logger = logging.getLogger(__name__)

class TrackedOntology(Protocol):
    version: Tracked|Version|VersionStored
    graph: TrackedGraph|nx.DiGraph
    licence: int|None
    copyright: int|None
    changed: bool

class VersionChange(IntEnum):
    MAJOR = 0
    MINOR = 1
    PATCH = 2

class Neo4jOntologyRepository(BaseRepository):
    # entry attributes that require forking to a new entry when changed
    material_changes: Set[str] = {
        'name',
        'type',
        'categories'
        'trait', 'condition', 'exposure','method','scale'
    }
    def __init__(self, tx: AsyncTransaction):
        super().__init__()
        self.tx = tx

    async def get_latest_version(self) -> VersionStored | None:
        result = await self.tx.run(queries['ontologies']['get_latest_version'])
        record = await result.single()
        if record is not None:
            return VersionStored(**record['version'])

    async def get_next_version(self, version_change: VersionChange = VersionChange.PATCH) -> Version:
        latest_version = await self.get_latest_version()
        if latest_version is None:  # i.e. None yet stored
            version = Version(major=0, minor=0, patch=0, comment='default')
        else:
            if version_change is VersionChange.PATCH:
                version = Version(
                    major=latest_version.major,
                    minor=latest_version.minor,
                    patch=latest_version.patch + 1,
                    comment='default'
                )
            elif version_change is VersionChange.MINOR:
                version = Version(
                    major=latest_version.major,
                    minor=latest_version.minor + 1,
                    patch=0,
                    comment='default'
                )
            else:  # version_change is VersionChange.MAJOR
                version = Version(
                    major=latest_version.major + 1,
                    minor=0,
                    patch=0,
                    comment='default'
                )
        return version

    async def _create(self, version: Version|None = None) -> Ontology:
        """
        This will create a fork of the latest version.

        If no version is specified, a major version change will be applied.
        If no ontology version exists a new empty Ontology will be created.

        """
        latest = await self.get_latest_version()
        if version is None:
            version = await self.get_next_version(version_change=VersionChange.MAJOR)
        else:
            if not version > latest:
                raise ValueError(f"New version numbers must be higher than the latest stored version: {latest}")

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
    )-> None:
        new_version = await self.get_next_version(version_change)

        result = await self.tx.run(
            queries['ontologies']['fork_version'],
            version_id=ontology.version.id,
            major=new_version.major,
            minor=new_version.minor ,
            patch=new_version.patch,
            comment=new_version.comment
        )
        record = await result.single()
        new_version_stored = VersionStored(**record['version'])
        ontology.version = new_version_stored

    async def _get(self, version_id: int = None) -> Ontology|None:
        if version_id is None:
            version = await self.get_latest_version()
            if version is None:
                return None

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

    async def _update_entry(self, entry: OntologyEntry) -> OntologyEntry:
        params = entry.model_dump()
        entry_id = params.pop('id')
        authors = params.pop('authors')
        references = params.pop('references')
        query = ontology_entries.update_ontology_entry(entry.label)
        result = await self.tx.run(
            query=query,
            params=params,
            authors=authors,
            references=references,
            entry_id=entry_id
        )
        record = await result.single()
        return self.record_to_entry(record['entry'])

    async def _remove_entry(self, entry: OntologyEntry, version_id: int) -> None:
        await self.tx.run(queries['ontologies']['remove_entry'], entry=entry.id, version=version_id)

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


