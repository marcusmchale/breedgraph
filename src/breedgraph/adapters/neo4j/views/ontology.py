from neo4j import AsyncSession, AsyncResult, Record, AsyncTransaction
from neo4j.exceptions import ResultNotSingleError
from collections import defaultdict
from dataclasses import fields

from breedgraph.domain.model.time_descriptors import deserialize_time

from breedgraph.domain.model.ontology import (
    OntologyCommit,
    Version,
    OntologyEntryLabel,
    ControlMethodType,
    ObservationMethodType,
    ScaleType,
    AxisType,
    OntologyRelationshipLabel, EntryLifecycle, RelationshipLifecycle, LifecyclePhase
)

from breedgraph.service_layer.queries.views import AbstractOntologyView
from breedgraph.service_layer.queries.read_models import (
    Ontology,
    OntologyEntryOutput,
    OntologyViewMode,
    OntologyRelationshipOutput
)

from breedgraph.service_layer.mappers import ontology_mapper
from breedgraph.adapters.neo4j.cypher import queries

from typing import List, Tuple, Optional

import logging
logger = logging.getLogger(__name__)


class Neo4jOntologyView(AbstractOntologyView):

    QUERY_MAP = {
        'ontology': {
            OntologyViewMode.EDITORIAL: {
                'current': queries['ontology']['ontology_editorial']
            },
            OntologyViewMode.PUBLISHED: {
                'current': queries['ontology']['ontology_published'],
                'historic': queries['ontology']['ontology_published_historic']
            }
        },
        'entries': {
            OntologyViewMode.EDITORIAL: {
                'current': {
                    'id': queries['ontology']['ontology_entries_editorial'],
                    'label': queries['ontology']['ontology_entries_by_label_editorial']
                }
            },
            OntologyViewMode.PUBLISHED: {
                'current': {
                    'id': queries['ontology']['ontology_entries_published'],
                    'label': queries['ontology']['ontology_entries_by_label_published']
                },
                'historic': {
                    'id': queries['ontology']['ontology_entries_published_historic'],
                    'label': queries['ontology']['ontology_entries_by_label_published_historic']
                }
            },
        },
        'relationships': {
            OntologyViewMode.EDITORIAL: {
                'current': queries['ontology']['ontology_relationships_editorial']
            },
            OntologyViewMode.PUBLISHED: {
                'current': queries['ontology']['ontology_relationships_published'],
                'historic': queries['ontology']['ontology_relationships_published_historic']
            }
        }
    }

    def __init__(self, session: AsyncSession):
        super().__init__()
        self.session = session
        #todo ontology mapper might be class attribute
        self.ontology_mapper = ontology_mapper

    async def _get_current_version(self, tx: AsyncTransaction|None = None) -> Version:
        if tx is not None:
            return await self._get_current_version_tx(tx)

        async with await self.session.begin_transaction() as tx:
            return await self._get_current_version_tx(tx)

    @staticmethod
    async def _get_current_version_tx(tx: AsyncTransaction):
        query = queries['ontology']['get_latest_version']
        result = await tx.run(query)
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

    @staticmethod
    def get_label_from_record(record: Record|dict):
        entry = record.get('entry', record)  # Fallback to record if no 'entry' key
        try:
            return OntologyEntryLabel(entry.get('label'))
        except TypeError:
            raise ValueError("Record does not contain a label field")
        except ValueError:
            raise ValueError(f"Label is not recognized as a valid ontology entry label: {entry.get('label')}")

    def get_entry_class_from_record(self, record: Record|dict):
        label = self.get_label_from_record(record)
        entry_class = self.ontology_mapper.get_entry_output_class_mapping().get(label)
        if not entry_class:
            raise ValueError(f"No entry output class found for label: {label}")
        return entry_class

    @staticmethod
    def coerce_intrinsic_attributes(entry_dict: dict):
        lifecycle = EntryLifecycle(**entry_dict.pop('lifecycle'))
        entry_dict['phase'] = lifecycle.current_phase

        if 'scale_type' in entry_dict:
            entry_dict['scale_type'] = ScaleType(entry_dict['scale_type'])
        if 'observation_type' in entry_dict:
            entry_dict['observation_type'] = ObservationMethodType(entry_dict['observation_type'])
        if 'control_type' in entry_dict:
            entry_dict['control_type'] = ControlMethodType(entry_dict['control_type'])
        if 'axes' in entry_dict:
            entry_dict['axes'] = tuple(AxisType(a) for a in entry_dict['axes'])

    @staticmethod
    def filter_dict(entry_dict: dict, node_class):
        # Filter entry_dict to only include fields that exist on the node class
        node_fields = {f.name for f in fields(node_class)}
        return {k: v for k, v in entry_dict.items() if k in node_fields}

    def record_to_entry(
            self,
            record: Record|dict,
            version: Version,
            view: OntologyViewMode
    ) -> OntologyEntryOutput:
        entry_class = self.get_entry_class_from_record(record)
        entry_dict = record.get('entry', {})
        entry_dict.pop('label', None)

        self.coerce_intrinsic_attributes(entry_dict)

        entry_patches = entry_dict.get('patches', [])
        for patch in entry_patches:
            entry_dict.update(patch)

        entry_dict = self.filter_dict(entry_dict, entry_class)

        relationship_dicts = record.get('relationships', [])
        attr_rels = defaultdict(list)
        for relationship_dict in relationship_dicts:
            # To return fully hydrated views of the entries as nodes that incorporate relationship details.
            # This helps in preselecting values in forms and simplifying other interfaces
            # filter by lifecycles first
            lifecycle = RelationshipLifecycle(**relationship_dict.get('lifecycle'))
            if lifecycle.current_phase in [LifecyclePhase.DEPRECATED, LifecyclePhase.REMOVED]:
                continue
            elif lifecycle.current_phase is LifecyclePhase.DRAFT and view is OntologyViewMode.PUBLISHED:
                continue
            # then add to map from attr to rel if not filtered out
            is_source = relationship_dict['source_id'] == entry_dict['id']
            attr = self.ontology_mapper.get_attribute_name(
                source_label=OntologyEntryLabel(relationship_dict['source_label']),
                target_label=OntologyEntryLabel(relationship_dict['target_label']),
                attr_for_source=is_source
            )
            attr_rels[attr].append(relationship_dict)

        attr_types = {f.name: f.type for f in fields(entry_class)}
        # now sort the values and set lists to tuples/ints to complete the entry
        for attr, rels in attr_rels.items():
            if attr == 'categories':
                rels.sort(key=ontology_mapper.get_rank)
            else:
                rels.sort(key=lambda x: x.get('id'))

            attr_type = attr_types.get(attr)
            if not attr_type:
                raise ValueError(f"Unexpected attribute: {attr} for class {entry_class}")
            if attr_type in [Tuple[int, ...], Optional[Tuple[int, ...]]]:
                value = [rel.get('target_id' if rel.get('source_id') == entry_dict['id'] else 'source_id') for rel in
                         rels]
                entry_dict[attr] = tuple(value)
            elif attr_type in [int, Optional[int]]:
                rel = rels[0] if rels else None
                if rel:
                    entry_dict[attr] = rel.get(
                        'target_id' if rel.get('source_id') == entry_dict['id'] else 'source_id'
                    )
            else:
                raise ValueError(f"Unexpected attribute type: {attr_type} for relationship")

        entry = entry_class(**entry_dict, version=version, view=view)
        return entry

    @staticmethod
    def record_to_relationships(record: Record, version: Version, view: OntologyViewMode) -> List[OntologyRelationshipOutput]:
        relationships = list()
        relationship_dicts = record.get('relationships')
        for relationship_dict in relationship_dicts:
            patches = relationship_dict.get('patches', [])
            for patch in patches:
                relationship_dict.update(patch)

            relationships.append(
                OntologyRelationshipOutput(
                    label=OntologyRelationshipLabel(relationship_dict['relationship_type']),
                    id=relationship_dict['id'],
                    version=version,
                    source_id=relationship_dict['source_id'],
                    target_id=relationship_dict['target_id'],
                    phase=RelationshipLifecycle(**relationship_dict['lifecycle']).current_phase,
                    rank=relationship_dict.get('rank'),
                    view=view
                )
            )
        return relationships

    async def _get_ontology(self, version: Version, view: OntologyViewMode) -> Ontology:
        entries: List[OntologyEntryOutput] = []
        relationships: List[OntologyRelationshipOutput] = []
        async with await self.session.begin_transaction() as tx:
            current_version = await self._get_current_version_tx(tx)
            version_type = 'current' if current_version == version else 'historic'
            if view == OntologyViewMode.EDITORIAL and version_type == 'historic':
                raise ValueError("Editorial view is only supported for the current version")
            query = self.QUERY_MAP['ontology'][view][version_type]

            params = {'version': version.packed_version}
            result: AsyncResult = await tx.run(query, **params)
            async for record in result:
                entries.append(self.record_to_entry(record, version, view))
                relationships.extend(self.record_to_relationships(record, version, view))
            return Ontology(
                version=version,
                view=view,
                entries=tuple(entries),
                relationships=tuple(relationships)
            )

    async def _get_entries(
        self,
        version: Version,
        view: OntologyViewMode,
        entry_ids: list[int] | None = None,
        labels: list[OntologyEntryLabel] | None = None
    ) -> List[OntologyEntryOutput]:
        if not entry_ids and not labels:
            return []
        if entry_ids and labels:
            raise ValueError("Specify either entry_ids or labels, not both.")

        async with await self.session.begin_transaction() as tx:
            current_version = await self._get_current_version_tx(tx)
            version_type = 'current' if current_version == version else 'historic'
            if view == OntologyViewMode.EDITORIAL and version_type == 'historic':
                raise ValueError("Editorial view is only supported for the current version")

            filter_type = 'id' if entry_ids else 'label'
            query = self.QUERY_MAP['entries'][view][version_type][filter_type]

            if entry_ids:
                params = {
                    'entry_ids': entry_ids,
                    'version': version.packed_version
                }
            elif labels:
                params = {
                    'labels': [l.value for l in labels],
                    'version': version.packed_version
                }

            result: AsyncResult = await tx.run(query, **params)
            return [self.record_to_entry(record, version, view) async for record in result]

    async def _get_relationships(
        self,
        entry_ids: list[int],
        version: Version,
        view: OntologyViewMode
    ) -> List[OntologyRelationshipOutput]:
        async with await self.session.begin_transaction() as tx:
            current_version = await self._get_current_version_tx(tx)
            version_type = 'current' if current_version == version else 'historic'
            if view == OntologyViewMode.EDITORIAL and version_type == 'historic':
                raise ValueError("Editorial view is only supported for the current version")

            query = self.QUERY_MAP['relationships'][view][version_type]
            params = {
                'entry_ids': entry_ids,
                'version': version.packed_version
            }
            result: AsyncResult = await tx.run(query, **params)
            record = await result.single(strict=True)
            return self.record_to_relationships(record, version=version, view=view)


    @staticmethod
    def record_to_commit(record) -> OntologyCommit:
        commit_data = record['commit']
        commit_data['time'] = deserialize_time(commit_data['time'])
        commit_data['version'] = Version.from_packed(commit_data['version'])
        return OntologyCommit(**commit_data)

    async def _get_commits(self, limit: int|None = None, last_version_id: int|None = None) -> List[OntologyCommit]:
        async with await self.session.begin_transaction() as tx:
            if limit is None and last_version_id is None:
                query = queries['ontology']['get_commit_history']
                result = await tx.run(query)
            elif limit is None and last_version_id is not None:
                query = queries['ontology']['get_commit_history_with_last_version']
                result = await tx.run(query, last_version=last_version_id)

            elif limit is not None and last_version_id is None:
                query = queries['ontology']['get_commit_history_with_limit']
                result = await tx.run(query, limit=limit)

            else:
                query = queries['ontology']['get_commit_history_pagination']
                result = await tx.run(query, limit=limit, last_version=last_version_id)

            return [self.record_to_commit(record) async for record in result]