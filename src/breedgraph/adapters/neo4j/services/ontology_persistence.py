from collections import defaultdict

from neo4j import AsyncTransaction, Record
from neo4j.exceptions import ResultNotSingleError

from breedgraph.custom_exceptions import IllegalOperationError
from breedgraph.service_layer.persistence.ontology import OntologyPersistenceService

from breedgraph.adapters.neo4j.cypher import queries, ontology

# Import all ontology entry types - this ensures all subclasses are registered
from breedgraph.domain.model.ontology import *
from breedgraph.domain.model.accounts import OntologyRole

from typing import List, Set, Optional, Dict, Any, Tuple, AsyncGenerator, Type

import logging
logger = logging.getLogger(__name__)


class Neo4jOntologyPersistenceService(OntologyPersistenceService):
    """Neo4j implementation of the ontology persistence service."""

    def __init__(self, tx: AsyncTransaction):
        self.tx = tx
        self._current_version_cache: Version | None = None

    async def get_user_ontology_role(self, user_id: int):
        query = queries['accounts']['get_user_ontology_role']
        result = await self.tx.run(query, user_id = user_id)
        record = await result.single()
        if record is None:
            raise ValueError(f"User with id {user_id} not found")
        return OntologyRole(record.value()) if record.value() else OntologyRole.VIEWER

    def record_to_entry(self, record: Record) -> OntologyEntryStored:
        entry_dict = record['entry']
        patches = record.get('patches', [])
        for patch in patches:
            entry_dict.update(patch)

        # remove lowercase name from record
        entry_dict.pop('name_lower')
        # replace strings with enums
        if 'scale_type' in entry_dict:
            entry_dict['scale_type'] = ScaleType(entry_dict['scale_type'])
        if 'observation_type' in entry_dict:
            entry_dict['observation_type'] = ObservationMethodType(entry_dict['observation_type'])
        if 'control_type' in entry_dict:
            entry_dict['control_type'] = ControlMethodType(entry_dict['control_type'])
        if 'axes' in entry_dict:
            entry_dict['axes'] = [AxisType(a) for a in entry_dict['axes']]

        # Extract the label from the record
        label_str: str|None = entry_dict.pop('label')
        try:
            label = OntologyEntryLabel(label_str)
        except TypeError:
            raise ValueError("Record does not contain a label field")
        except ValueError:
            raise ValueError(f"Label is not recognized as a valid ontology entry label: {label_str}")

        entry_class = self.ontology_mapper.get_stored_class_mapping().get(label)

        if entry_class is None:
            raise ValueError(f"No class found for label: {label}")

        return entry_class(**entry_dict)

    @staticmethod
    def record_to_relationship(record: Record) -> OntologyRelationshipBase:
        relationship_dict = record.get('relationship', {})
        if not relationship_dict.get('id'):
            raise ValueError("Relationship id not created/found")
        relationship_dict['relationship_id'] = relationship_dict.pop('id')
        for patch in record.get('patches', []):
            relationship_dict.update(patch)

        return OntologyRelationshipBase.relationship_from_label(**relationship_dict)

    async def get_current_version(self) -> Version:
        if self._current_version_cache is None:
            latest_version = await self._get_latest_version()
            self._current_version_cache = latest_version
            return latest_version
        else:
            return self._current_version_cache

    async def entries_exist(self, entry_ids: List[int]) -> Dict[int, bool]:
        query = queries['ontology']['entries_exist']
        result = await self.tx.run(query, entry_ids=entry_ids)
        return {record.get('id'): record.get('exists') async for record in result}

    async def entries_exist_for_label(self, entry_ids: List[int], label: OntologyEntryLabel) -> Dict[int, bool]:
        query = ontology.entries_exist_by_label(labels=[label])
        result = await self.tx.run(query, entry_ids=entry_ids)
        return {record.get('id'): record.get('exists') async for record in result}

    async def _create_entry(self, entry: OntologyEntryInput, user_id: int) -> OntologyEntryStored:
        version = await self.get_current_version()
        params = entry.model_dump()
        params['name_lower'] = params['name'].casefold()
        authors = params.pop('authors')
        references = params.pop('references')
        query = ontology.create_ontology_entry(entry.label)
        result = await self.tx.run(
            query=query,
            params=params,
            authors=authors,
            references=references,
            user_id=user_id,
            version=version.packed_version
        )
        record = await result.single(strict=True)
        return self.record_to_entry(record)

    @staticmethod
    def dict_diff(old, new):
        return {
            key: new[key]
            for key in new
            if old.get(key) != new[key]
        }

    async def update_entry(self, entry: OntologyEntryStored, user_id: int) -> None:
        version = await self.get_current_version()

        stored_entry = await self.get_entry(entry_id=entry.id)
        if not stored_entry:
            raise ValueError("Could not find existing entry to update it")
        # get existing record to compare for patch params
        diff = self.dict_diff(stored_entry.model_dump(), entry.model_dump())

        if 'name' in diff:
            diff['name_lower'] = diff['name'].casefold()

        diff.pop('authors', None)
        authors_added = list(set(entry.authors) - set(stored_entry.authors))
        authors_removed = list(set(stored_entry.authors) - set(entry.authors))
        diff.pop('references', None)
        references_added = list(set(entry.references) - set(stored_entry.references))
        references_removed = list(set(stored_entry.references) - set(entry.references))

        query = queries['ontology']['patch_entry_attributes']

        await self.tx.run(
            query=query,
            entry_id=entry.id,
            params=diff,
            authors_added=authors_added,
            references_added=references_added,
            authors_removed=authors_removed,
            references_removed=references_removed,
            user_id=user_id,
            version=version.packed_version
        )

    async def create_relationship(self, relationship: OntologyRelationshipBase, user_id: int) -> OntologyRelationshipBase:
        """Create a new relationship between entries."""
        logger.debug(
            f"Creating relationship: {str(relationship)})"
        )
        version = await self.get_current_version()

        dump = relationship.model_dump()
        query = ontology.create_ontology_relationship(
            label=dump.pop('label'),
            source_label=dump.pop('source_label'),
            target_label=dump.pop('target_label')
        )
        if dump.pop('id') is not None:
            raise(ValueError("Relationship is already stored"))
        result = await self.tx.run(
            query,
            source_id=dump.pop('source_id'),
            target_id=dump.pop('target_id'),
            attributes = dump,
            user_id=user_id,
            version=version.packed_version
        )
        record = await result.single(strict=True)
        return self.record_to_relationship(record)

    async def update_relationship(self, relationship: OntologyRelationshipBase, user_id: int) -> None:
        """Update relationship attributes, e.g. rank"""
        logger.debug(
            f"Updating relationship: {str(relationship)})"
        )
        version = await self.get_current_version()
        dump = relationship.model_dump()
        fixed_fields = ['label', 'source_label', 'target_label', 'id', 'source_id', 'target_id']
        attributes = {key: value for key, value in dump.items() if key not in fixed_fields}

        stored_relationship = await self.get_relationship(relationship_id=relationship.id)
        stored_dump = stored_relationship.model_dump()
        stored_attributes = {key: stored_dump[key] for key in attributes.keys()}
        diff = self.dict_diff(stored_attributes, attributes)
        if diff:
            query = queries['ontology']['patch_relationship_attributes']
            await self.tx.run(
                query,
                relationship_id=relationship.id,
                attributes=diff,
                user_id=user_id,
                version=version.packed_version
            )

    async def get_entry(
            self,
            entry_id: int | None = None,
            name: str | None = None,
            label: OntologyEntryLabel | None = None
    ) -> OntologyEntryStored | None:
        matched_entry = None
        count = 0
        async for entry in self.get_entries(
            entry_ids=[entry_id] if entry_id is not None else [],
            labels=[label] if label is not None else [],
            names=[name] if name is not None else []
        ):
            count += 1
            if count == 1:
                matched_entry = entry
            else:
                raise ValueError("The filters provided match multiple entries")
        return matched_entry


    async def get_entries(
            self,
            version: Version | None = None,
            phases: List[LifecyclePhase] | None = None,
            entry_ids: List[int]|None = None,
            labels: List[OntologyEntryLabel]|None = None,
            names: List[str]|None = None
    ) -> AsyncGenerator[OntologyEntryStored, None]:
        current_version = await self.get_current_version()
        if version is None:
            version = current_version
        else:
            if names and version != current_version:
                raise ValueError("Name queries are only supported for the current version")

        if phases is None:
            phases = [LifecyclePhase.DRAFT, LifecyclePhase.ACTIVE, LifecyclePhase.DEPRECATED]
        query = ontology.get_entries(
            entry_ids=entry_ids,
            phases=phases,
            labels=labels,
            names=names
        )
        params = dict()
        params["version"] =version.packed_version
        # Entry IDs parameter (if specified)
        if entry_ids:
            params["entry_ids"] = entry_ids
        # Names parameter (if specified) - convert to lowercase for matching
        if names:
            params["names_lower"] = [name.casefold() for name in names]
        result = await self.tx.run(query, **params)
        async for record in result:
            yield self.record_to_entry(record)

    async def get_relationship(self, relationship_id: int, version:Version|None = None) -> OntologyRelationshipBase | None:
        if version is None:
            version = await self.get_current_version()

        query = queries['ontology']['get_relationship']
        result = await self.tx.run(query, relationship_id=relationship_id, version=version.packed_version)
        record = await result.single()
        if record is None:
            return None
        else:
            return self.record_to_relationship(record)


    async def _get_relationships(
            self,
            version: Version,
            phases: List[LifecyclePhase],
            labels: List[OntologyRelationshipLabel] | None = None,
            entry_ids: List[int] | None = None,
            source_ids: List[int] | None = None,
            target_ids: List[int] |None = None
    ) -> AsyncGenerator[OntologyRelationshipBase, None]:
        query = ontology.get_relationships(
            phases=phases,
            labels=labels,
            entry_ids=entry_ids,
            source_ids=source_ids,
            target_ids=target_ids
        )
        params = {"version": version.packed_version}
        # Entry ID parameters (if specified)
        if entry_ids:
            params["entry_ids"] = entry_ids
        if source_ids:
            params["source_ids"] = source_ids
        if target_ids:
            params["target_ids"] = target_ids
        result = await self.tx.run(query, **params)
        async for record in result:
            yield self.record_to_relationship(record)

    async def get_entry_lifecycles(self, entry_ids: List[int]) -> Dict[int, EntryLifecycle]:
        query = queries['ontology']['get_entry_lifecycles']
        result = await self.tx.run(query, entry_ids=entry_ids)
        lifecycles = {}
        async for record in result:
            lifecycle_record = record.get('lifecycle')
            lifecycles[lifecycle_record.get('entry_id')] = EntryLifecycle.from_record(lifecycle_record)
        return lifecycles

    async def get_relationship_lifecycles(self, relationship_ids: List[int]) -> Dict[int, RelationshipLifecycle]:
        query = queries['ontology']['get_relationship_lifecycles']
        result = await self.tx.run(query, relationship_ids=relationship_ids)
        lifecycles = {}
        async for record in result:
            lifecycle_record = record.get('lifecycle')
            lifecycles[lifecycle_record.get('relationship_id')] = RelationshipLifecycle.from_record(lifecycle_record)
        return lifecycles

    # Lifecycle persistence
    async def save_entry_lifecycles(
            self,
            lifecycles: Dict[int, EntryLifecycle],
            user_id: int
    ) -> None:
        if user_id is None:
            raise IllegalOperationError("Changing lifecycles requires user_id for audit")
        """Save entry lifecycles to persistent storage."""
        logger.debug(f"Saving {len(lifecycles)} entry lifecycles")
        lifecycles = [
            lifecycle.model_dump() for lifecycle in lifecycles.values()
        ]
        query = queries['ontology']['save_entry_lifecycles']
        await self.tx.run(query, lifecycles=lifecycles, user_id = user_id)

    async def save_relationship_lifecycles(
            self,
            lifecycles: Dict[int, RelationshipLifecycle],
            user_id: int
    ) -> None:
        if user_id is None:
            raise IllegalOperationError("Changing lifecycles requires user_id for audit")
        """Save relationship lifecycles to persistent storage."""
        logger.debug(f"Saving {len(lifecycles)} relationship lifecycles")
        lifecycles = [
            lifecycle.model_dump() for lifecycle in lifecycles.values()
        ]
        if lifecycles:
            query = queries['ontology']['save_relationship_lifecycles']
            await self.tx.run(query, lifecycles=lifecycles, user_id=user_id)

    async def activate_drafts(self, version: Version, user_id: int):
        query = queries['ontology']['activate_drafts']
        await self.tx.run(query, version=version.packed_version, user_id=user_id)

    async def remove_deprecated(self, version: Version, user_id: int):
        query = queries['ontology']['remove_deprecated']
        await self.tx.run(query, version=version.packed_version, user_id=user_id)

    async def name_in_use(
            self,
            label: str,
            name: str,
            exclude_id: int|None = None
    ) -> bool:
        """Check if name is already in use for a specific entry type."""
        logger.debug(f"Checking names uniqueness: {name} for type {label}")
        result = await self.tx.run(
            ontology.name_in_use(label),
            name_lower=name.casefold(),
            exclude_id=exclude_id
        )
        record = await result.single()
        return record.get('exists')

    async def abbreviation_in_use(
            self,
            label: str,
            abbreviation: str,
            exclude_id: int|None = None
    ) -> bool:
        """Check if name is already in use for a specific entry type."""
        logger.debug(f"Checking abbreviation uniqueness: {abbreviation} for type {label}")
        result = await self.tx.run(
            ontology.abbreviation_in_use(label),
            abbreviation_lower=abbreviation.casefold(),
            exclude_id=exclude_id
        )
        record = await result.single()
        return record.get('exists')

    async def get_entry_types(self, entry_ids: List[int]) -> Dict[int, str]:
        entry_types = {}
        async for entry in self.get_entries(entry_ids = entry_ids):
            entry_types[entry.id] = entry.label
        return entry_types

    async def has_path_between_entries(
            self,
            source_id: int,
            target_id: int,
            relationship_type: OntologyRelationshipLabel
    ) -> bool:
        """Check if there's a path between two entries (for cycle detection)."""
        logger.debug(f"Checking path between entries: {source_id} -> {target_id}")
        query = ontology.has_path_between_entries(label=relationship_type)
        result = await self.tx.run(query, source_id=source_id, target_id=target_id)
        record = await result.single(strict=True)
        return record['has_path']

    async def get_entry_dependencies(self, entry_id: int) -> List[int]:
        """Get all entries that depend on this entry (incoming relationships)."""
        logger.debug(f"Getting guards for entry: {entry_id}")

        query = """
        MATCH (source:OntologyEntry)-[r:ONTOLOGY_RELATIONSHIP]->(target:OntologyEntry {id: $entry_id})
        RETURN collect(DISTINCT source.id) as guards
        """
        result = await self.tx.run(query, entry_id=entry_id)
        record = await result.single()
        return record["guards"] if record else []

    async def _get_latest_version(self) -> Version:
        query = queries['ontology']['get_latest_version']
        result = await self.tx.run(query)
        try:
            record = await result.single(strict=True)
            return Version.from_packed(record["commit.version"])
        except ResultNotSingleError:
            logger.debug("No version found, returning initial version")

        return Version(
            major=0,
            minor=0,
            patch=0
        )

    async def _commit_version(self, user_id: int,  commit: OntologyCommit):
        # before commit, update source nodes with patches
        await self.apply_patches()

        await self.tx.run(
            queries['ontology']['commit_version'],
            user_id=user_id,
            version=commit.version.packed_version,
            comment=commit.comment,
            licence=commit.licence,
            copyright=commit.copyright
        )
        self._current_version_cache = commit.version

    async def _apply_entry_patches(self, version: Version):
        get_patches_query = queries['ontology']['get_entry_patches']
        patches_result = await self.tx.run(
            get_patches_query,
            version=version.packed_version
        )

        collated_patches = defaultdict(dict)
        async for record in patches_result:
            entry_id = record['entry_id']
            patches = record['patches']

            for patch in patches:
                collated_patches[entry_id].update(patch)

        apply_patches_query = queries['ontology']['apply_entry_patches']
        await self.tx.run(
            apply_patches_query,
            patches=[{'entry_id': entry_id, 'patch': patch} for entry_id, patch in collated_patches.items()]
        )

    async def _apply_relationship_patches(self, version: Version):
        get_patches_query = queries['ontology']['get_relationship_patches']
        patches_result = await self.tx.run(
            get_patches_query,
            version=version.packed_version
        )

        collated_patches = defaultdict(dict)
        async for record in patches_result:
            relationship_id = record['relationship_id']
            patches = record['patches']

            for patch in patches:
                collated_patches[relationship_id].update(patch)

        apply_patches_query = queries['ontology']['apply_relationship_patches']
        await self.tx.run(
            apply_patches_query,
            patches=[{'relationship_id': relationship_id, 'patch': patch} for relationship_id, patch in collated_patches.items()]
        )

    async def apply_patches(self):
        version: Version = await self.get_current_version()
        await self._apply_entry_patches(version)
        await self._apply_relationship_patches(version)
