from neo4j import AsyncTransaction, Record
from neo4j.exceptions import ResultNotSingleError

from breedgraph.custom_exceptions import IllegalOperationError
from breedgraph.domain.model.time_descriptors import deserialize_time
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
        query = ontology.patch_ontology_entry(entry.label)
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
            user_id=user_id
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
        stored_attributes = {key: stored_dump[key] for key, in attributes.keys()}
        diff = self.dict_diff(stored_attributes, attributes)
        query = queries['ontology']['patch_relationship_attributes']
        await self.tx.run(
            query,
            relationship_id=relationship.id,
            attributes=diff,
            user_id=user_id,
            version=version.packed_version
        )

    async def get_entries(
            self,
            version: Version | None = None,
            phases: List[LifecyclePhase] | None = None,
            entry_ids: List[int] = None,
            labels: List[OntologyEntryLabel]|None = None,
            names: List[str]|None = None
    ) -> AsyncGenerator[OntologyEntryStored, None]:
        if version is None:
            version = await self.get_current_version()
        if phases is None:
            phases = [LifecyclePhase.DRAFT, LifecyclePhase.ACTIVE, LifecyclePhase.DEPRECATED]
        query = ontology.get_entries(
            entry_ids = entry_ids,
            phases=phases,
            labels=labels,
            names=names
        )
        params = { "version": version.packed_version }
        # Entry IDs parameter (if specified)
        if entry_ids:
            params["entry_ids"] = entry_ids
        # Names parameter (if specified) - convert to lowercase for matching
        if names:
            params["names_lower"] = [name.casefold() for name in names]
        result = await self.tx.run(query, **params)
        async for record in result:
            yield self.record_to_entry(record)

    async def get_entry(
            self,
            entry_id: int | None = None,
            name: str | None = None,
            label: OntologyEntryLabel | None = None,
            version: Version | None = None,
            phases: List[LifecyclePhase] | None = None
    ) -> OntologyEntryStored | None:
        matched_entry = None
        count = 0
        async for entry in self.get_entries(
            entry_ids=[entry_id] if entry_id is not None else [],
            version=version,
            phases=phases,
            labels=[label] if label is not None else [],
            names=[name] if name is not None else []
        ):
            count += 1
            if count == 1:
                matched_entry = entry
            else:
                raise ValueError("The filters provided match multiple entries")
        return matched_entry

    async def get_relationship(self, relationship_id: int) -> OntologyRelationshipBase | None:
        query = queries['ontology']['get_relationship']
        result = await self.tx.run(query, relationship_id=relationship_id)
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

    async def set_scale_categories_ranks(
            self,
            scale_id: int,
            categories: List[int],
            ranks: List[int]
    ) -> None:
        """Set the ranks for categories of a scale"""
        if not len(categories) == len(ranks):
            raise ValueError("A rank must be provided for all categories")
        logger.debug(f"Setting ranks for {len(categories)} categories of scale {scale_id}")
        query = queries['ontology']['set_scale_categories_ranks']
        await self.tx.run(query, scale_id=scale_id, categories=categories, ranks=ranks)

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
        logger.debug(f"Getting dependencies for entry: {entry_id}")

        query = """
        MATCH (source:OntologyEntry)-[r:ONTOLOGY_RELATIONSHIP]->(target:OntologyEntry {id: $entry_id})
        RETURN collect(DISTINCT source.id) as dependencies
        """
        result = await self.tx.run(query, entry_id=entry_id)
        record = await result.single()
        return record["dependencies"] if record else []

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
        await self.tx.run(
            queries['ontology']['commit_version'],
            user_id=user_id,
            version=commit.version.packed_version,
            comment=commit.comment,
            licence=commit.licence,
            copyright=commit.copyright
        )
        self._current_version_cache = commit.version

    @staticmethod
    def record_to_commit(record) -> OntologyCommit:
        commit_data = record['commit']
        commit_data['time'] = deserialize_time(commit_data['time'])
        commit_data['version'] = Version.from_packed(commit_data['version'])
        return OntologyCommit(**commit_data)

    async def get_commits(self, version_min: Version|None = None, version_max: Version|None = None) -> AsyncGenerator[OntologyCommit, None]:
        query = queries['ontology']['get_commit_by_version_min_max']
        if version_min is None:
            version_min = 0
        else:
            version_min = version_min.packed_version

        if version_max is None:
            version_max = await self.get_current_version()
        version_max = version_max.packed_version

        result = await self.tx.run(query, version_min = version_min, version_max = version_max)
        async for record in result:
            yield self.record_to_commit(record)

    async def get_commit_history(self, limit: int|None = None) -> AsyncGenerator[OntologyCommit, None]:
        if limit is None:
            query = queries['ontology']['get_commit_history']
            result = await self.tx.run(query)
        else:
            query =queries['ontology']['get_commit_history_with_limit']
            result = await self.tx.run(query,limit = limit)

        async for record in result:
            yield self.record_to_commit(record)
