import re
from functools import lru_cache

from neo4j import AsyncTransaction, Record
from neo4j.exceptions import ResultNotSingleError, CypherSyntaxError, TransactionError, Neo4jError

from src.breedgraph.custom_exceptions import IllegalOperationError
from src.breedgraph.domain.model.time_descriptors import deserialize_time
from src.breedgraph.service_layer.persistence.ontology import OntologyPersistenceService

from src.breedgraph.adapters.neo4j.cypher import queries, ontology

# Import all ontology entry types - this ensures all subclasses are registered
from src.breedgraph.domain.model.ontology import *

from typing import List, Set, Optional, Dict, Any, Tuple, AsyncGenerator, Type

import logging
logger = logging.getLogger(__name__)


class Neo4jOntologyPersistenceService(OntologyPersistenceService):
    """Neo4j implementation of the ontology persistence service."""

    def __init__(self, tx: AsyncTransaction):
        self.tx = tx
        self._current_version_cache: Version | None = None

    def record_to_entry(self, record: Record, as_output=False) -> OntologyEntryStored | OntologyEntryOutput:
        record_dict = dict(record)
        # remove lowercase name from record
        record_dict.pop('name_lower')
        # replace strings with enums
        if 'scale_type' in record_dict:
            record_dict['scale_type'] = ScaleType(record_dict['scale_type'])
        if 'observation_type' in record_dict:
            record_dict['observation_type'] = ObservationMethodType(record_dict['observation_type'])
        if 'axes' in record_dict:
            record_dict['axes'] = [AxisType(a) for a in record_dict['axes']]

        # Extract the label from the record
        label_str: str|None = record_dict.pop('label')
        try:
            label = OntologyEntryLabel(label_str)
        except TypeError:
            raise ValueError("Record does not contain a label field")
        except ValueError:
            raise ValueError(f"Label is not recognized as a valid ontology entry label: {label_str}")

        # Get the appropriate entry class
        if as_output:
            entry_class = self.ontology_mapper.get_output_class_mapping().get(label)
        else:
            entry_class = self.ontology_mapper.get_stored_class_mapping().get(label)
        if entry_class is None:
            raise ValueError(f"No class found for label: {label}")

        # process relationship data (returned if output format is requested)
        if "relationships" in record_dict:
            for relationship in record_dict.pop('relationships'):
                is_source = relationship['source_id'] == record_dict['id']
                attr, _type = self.ontology_mapper.get_attribute_name_and_type(
                    source_label=OntologyEntryLabel(relationship['source_label']),
                    target_label=OntologyEntryLabel(relationship['target_label']),
                    attr_for_source=is_source
                )
                if attr in record_dict:
                    if _type == List[int]:
                        record_dict[attr].append(relationship['target_id' if is_source else 'source_id'])
                    else:
                        raise ValueError(f"Attribute {attr} already exists in record_dict")
                else:
                    if _type == List[int]:
                        record_dict[attr] = [relationship['target_id' if is_source else 'source_id']]
                    else:
                        record_dict[attr] = relationship['target_id' if is_source else 'source_id']
        return entry_class(**record_dict)

    @staticmethod
    def record_to_relationship(record: Record) -> OntologyRelationshipBase:
        record_dict = record.get('relationship') or dict(record)
        if not record_dict.get('relationship_id'):
            raise ValueError("Relationship id not created - this typically means a source or target node was not found")

        return OntologyRelationshipBase.relationship_from_label(**record_dict)


    async def get_current_version(self) -> Version:
        if self._current_version_cache is None:
            self._current_version_cache = await self._get_latest_version()
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
            user_id=user_id
        )
        record = await result.single()
        return self.record_to_entry(record['entry'])

    async def update_entry(self, entry: OntologyEntryStored, user_id: int) -> None:
        params = entry.model_dump()
        entry_id = params.pop('id')
        params['name_lower'] = params['name'].casefold()
        authors = params.pop('authors')
        references = params.pop('references')
        query = ontology.update_ontology_entry(entry.label)
        await self.tx.run(
            query=query,
            entry_id=entry_id,
            params=params,
            authors=authors,
            references=references,
            user_id=user_id
        )

    async def create_relationship(self, relationship: OntologyRelationshipBase) -> OntologyRelationshipBase:
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
            attributes = dump
        )
        record = await result.single()
        return self.record_to_relationship(record)

    async def update_relationship(self, relationship: OntologyRelationshipBase) -> None:
        """Update relationship attributes, e.g. rank"""
        logger.debug(
            f"Updating relationship: {str(relationship)})"
        )
        dump = relationship.model_dump()
        generic_fields = ['label', 'source_label', 'target_label', 'id', 'source_id', 'target_id']
        attributes = {key: value for key, value in dump.items() if key not in generic_fields}
        query = queries['ontology']['update_relationship_attributes']
        await self.tx.run(
            query,
            relationship_id=relationship.id,
            attributes=attributes
        )

    async def get_entries(
            self,
            version: Version | None = None,
            phases: List[LifecyclePhase] | None = None,
            entry_ids: List[int] = None,
            labels: List[OntologyEntryLabel]|None = None,
            names: List[str]|None = None,
            as_output: bool = False,
    ) -> AsyncGenerator[OntologyEntryStored|OntologyEntryOutput, None]:
        if version is None:
            version = await self.get_current_version()
        if phases is None:
            phases = [LifecyclePhase.DRAFT, LifecyclePhase.ACTIVE, LifecyclePhase.DEPRECATED]
        query = ontology.get_entries(
            entry_ids = entry_ids,
            phases=phases,
            labels=labels,
            names=names,
            with_relationships=as_output
        )
        params = {"version": version.packed_version}
        # Entry IDs parameter (if specified)
        if entry_ids:
            params["entry_ids"] = entry_ids
        # Names parameter (if specified) - convert to lowercase for matching
        if names:
            params["names_lower"] = [name.casefold() for name in names]
        result = await self.tx.run(query, **params)
        async for record in result:
            yield self.record_to_entry(record['entry'], as_output)

    async def get_entry(
            self,
            entry_id: int = None,
            name: str = None,
            label: OntologyEntryLabel = None,
            version: Version | None = None,
            phases: List[LifecyclePhase] = None,
            as_output: bool = False
    ) -> OntologyEntryStored | None:
        matched_entry = None
        count = 0
        async for entry in self.get_entries(
            entry_ids=[entry_id] if entry_id is not None else [],
            version=version,
            phases=phases,
            labels=[label] if label is not None else [],
            names=[name] if name is not None else [],
            as_output=as_output
        ):
            count += 1
            if count == 1:
                matched_entry = entry
            else:
                raise ValueError("The filters provided match multiple entries")
        return matched_entry

    async def get_relationships(
            self,
            version: Version | None = None,
            phases: List[LifecyclePhase] | None = None,
            labels: List[OntologyEntryLabel]|None = None,
            entry_ids: List[int] = None,
            source_ids: List[int] = None,
            target_ids: List[int] = None
    ) -> AsyncGenerator[OntologyRelationshipBase, None]:
        if version is None:
            version = await self.get_current_version()
        if phases is None:
            phases = [LifecyclePhase.DRAFT, LifecyclePhase.ACTIVE, LifecyclePhase.DEPRECATED]
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
            yield self.record_to_relationship(record['relationship'])

    async def get_relationships_by_sources_and_labels(
            self,
            source_ids: List[int],
            labels: List[OntologyRelationshipLabel]
    ) -> AsyncGenerator[OntologyRelationshipBase, None]:
        query = ontology.get_relationships_by_sources_and_labels(source_ids=source_ids, labels=labels)
        result = self.tx.run(query)
        async for record in result:
            yield self.record_to_relationship(record['relationship'])

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
        return {record.get('lifecycle').get('entry_id'): EntryLifecycle(**record['lifecycle']) async for record in result}

    async def get_relationship_lifecycles(self, relationship_ids: List[int]) -> Dict[int, RelationshipLifecycle]:
        query = queries['ontology']['get_relationship_lifecycles']
        result = await self.tx.run(query, relationship_ids=relationship_ids)
        return {record.get('lifecycle').get('relationship_id'): RelationshipLifecycle(**record['lifecycle']) async for record in result}

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

    async def get_scale_categories_with_ranks(self, scale_id: int) -> List[Tuple[int, Optional[int]]]:
        """Get categories for a scale with their ranks."""
        logger.debug(f"Getting scale categories with ranks for: {scale_id}")

        query = """
        MATCH (s:OntologyEntry {id: $scale_id})-[r:ONTOLOGY_RELATIONSHIP]->(c:OntologyEntry)
        WHERE r.label = 'HAS_CATEGORY'
        RETURN c.id as category_id, r.rank as rank
        ORDER BY r.rank NULLS LAST
        """

        result = await self.tx.run(query, scale_id=scale_id)
        categories = []

        async for record in result:
            categories.append((record["category_id"], record["rank"]))

        return categories

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
