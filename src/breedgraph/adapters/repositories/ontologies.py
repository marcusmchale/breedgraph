"""
Note there may be issues with consistency during edits due to shared nodes across versions.
e.g. if one user changes an attribute it may be lost/written over by another concurrent user
We force a fork on "material" changes so this won't happen when these details are changed,
 but e.g. reference edits may be lost.
 # todo consider how to handle this
"""

import logging
import re

from neo4j import AsyncTransaction, Record

from src.breedgraph.adapters.neo4j.cypher import queries, create_ontology_entry, update_ontology_entry
from src.breedgraph.adapters.repositories.trackable_wrappers import Tracked, TrackedDict
from src.breedgraph.adapters.repositories.base import BaseRepository

from typing import Set, AsyncGenerator, Protocol

from src.breedgraph.domain.model.ontologies import (
    Ontology, Version, VersionStored,
    OntologyEntry,
    # although the below may look unused they are accessed by globals below
    Term,
    Subject,
    Trait, Condition, Exposure,
    Method, Scale, Category,
    Variable, Parameter, Event,
    LocationType
)

logger = logging.getLogger(__name__)

class TrackedOntology(Protocol):
    version: Tracked|Version|VersionStored
    entries: TrackedDict

class Neo4jOntologyRepository(BaseRepository):
    # entry attributes that require forking to a new entry when changed
    material_changes: Set[str] = {
        'name',
        'description',
        'type'
    }
    optional_attributes: Set[str] = {
        'subjects',
        'type',
        'trait', 'condition', 'exposure',
        'method',
        'scale',
        'categories'
    }
    def __init__(self, tx: AsyncTransaction):
        super().__init__()
        self.tx = tx

    async def _create(self, ontology: Ontology, **kwargs) -> Ontology:
        ontology.version = await self._create_version(ontology.version)
        await self._set_licence(ontology.licence, ontology.version.id)
        await self._set_copyright(ontology.copyright, ontology.version.id)
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

    async def _get_versions(self):
        pass
        #version_tuple = re.split('\.|-', record['ontology']['version'], 3)
        #version = Version(
        #    major=int(version_tuple[0]),
        #    minor=int(version_tuple[1]),
        #    patch=int(version_tuple[2]),
        #    comment=version_tuple[3]
        #)

    async def _set_licence(self, licence_id: int, version_id: int) -> None:
        if licence_id is not None:
            await self.tx.run(
                queries['ontologies']['set_licence'],
                licence=licence_id,
                version=version_id
            )

    async def _set_copyright(self, copyright_id: int, version_id: int) -> None:
        if copyright_id is not None:
            await self.tx.run(
                queries['ontologies']['set_copyright'],
                copyright=copyright_id,
                version=version_id
            )

    async def _update_entries(self, entries: TrackedDict[int, Tracked|OntologyEntry], version_id):
        for entry_id in entries.added:
            entry = entries[entry_id]
            if entry.id < 0:
                 await self._create_entry(entry, version_id)
            else:
                # todo this is needed to support copying an entry from an earlier version
                raise NotImplementedError(
                    "An entry was added that was already stored,"
                    " support for this has not been implemented"
                )
        for entry_id in entries.changed:
            entry = entries[entry_id]
            if entry.changed.intersection(self.material_changes):
                # Fork to a new entry
                new_entry = await self._create_entry(entry, version_id)
                # Add this without tracking to the entries map
                entries.silent_set(new_entry.id, new_entry)
                # and remove the old one
                entries.silent_remove(entry_id)
                # move all mappings from the old reference to this new one.
                # todo work out how to apply this remapping,
                # need to actually change references in db, or do this during the fork?
            else:
                await self._update_entry(entry, version_id)

    async def _create_entry(self, entry: OntologyEntry, version_id: int) -> OntologyEntry:
        params = dict(entry)
        for p in self.optional_attributes:
            if not p in params:
                params[p] = None
        params['version_id'] = version_id
        query = create_ontology_entry(entry.__class__.__name__)
        result = await self.tx.run(
            query=query,
            **params
        )
        record = await result.single()
        return self.record_to_entry(record['entry'])

    async def _update_entry(self, entry: OntologyEntry, version_id: int) -> OntologyEntry:
        params = dict(entry)
        for p in self.optional_attributes:
            if not p in params:
                params[p] = None

        params['entry_id'] = entry.id
        query = update_ontology_entry(entry.__class__.__name__)
        result = await self.tx.run(
            query=query,
            **params
        )
        record = await result.single()
        return self.record_to_entry(record['entry'])

    @staticmethod
    def record_to_entry(record: Record) -> OntologyEntry:
        label = [l for l in record['labels'] if l != "OntologyEntry"][0]
        entry_class = globals()[label]
        return entry_class(**record)

    async def _get(self, version_id: int = None) -> Ontology|None:
        if version_id is not None:
            result = await self.tx.run(queries['ontologies']['get_ontology'], version_id=version_id)
            record = await result.single()
        else:
            result = await self.tx.run(queries['ontologies']['get_latest_ontology'], version_id=version_id)
            record = await result.single()
            if not record:
                new_ontology = await self._create(Ontology(version=Version(comment="default")))
                return new_ontology

        if record:
            return Ontology(
                version=VersionStored(**record['version']),
                entries={entry['id']: self.record_to_entry(entry) for entry in record['entries']}
            )
        else:
            return None

    def _get_all(self) -> AsyncGenerator[Ontology, None]:
        raise NotImplementedError

    async def _remove(self, ontology: Ontology) -> None:
        raise NotImplementedError

    async def _update(self, ontology: TrackedOntology):
        await self._update_entries(ontology.entries, ontology.version.id)
