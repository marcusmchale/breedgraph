from neo4j import AsyncSession, AsyncResult, Record
from neo4j.exceptions import ResultNotSingleError
from collections import defaultdict
from dataclasses import fields

from breedgraph.domain.model import LifecyclePhase
from breedgraph.domain.model.ontology import (
    Version,
    OntologyEntryLabel,
    ControlMethodType,
    ObservationMethodType,
    ScaleType,
    AxisType,
    OntologyRelationshipLabel, EntryLifecycle, RelationshipLifecycle
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

    def __init__(self, session: AsyncSession):
        super().__init__()
        self.session = session
        #todo ontology mapper might be class attribute
        self.ontology_mapper = ontology_mapper

    async def _get_current_version(self) -> Version:
        async with await self.session.begin_transaction() as tx:
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

        #entry_dict.pop('name_lower', None) # I think this is handled by filter_dict, i think?
        entry_dict = self.filter_dict(entry_dict, entry_class)

        relationship_dicts = record.get('relationships', [])
        attr_rels = defaultdict(list)
        for relationship_dict in relationship_dicts:
            # To return fully hydrated views of the entries as nodes that incorporate relationship details.
            # This helps in preselecting values in forms and simplifying other interfaces
            # start by building a map from attr to rel
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
            if 'properties' in relationship_dict:
                rank = relationship_dict.get('properties').get('rank')
            else:
                rank = None
            relationships.append(
                OntologyRelationshipOutput(
                    label=OntologyRelationshipLabel(relationship_dict['relationship_type']),
                    id=relationship_dict['id'],
                    version=version,
                    source_id=relationship_dict['source_id'],
                    target_id=relationship_dict['target_id'],
                    phase=RelationshipLifecycle(**relationship_dict['lifecycle']).current_phase,
                    rank=rank,
                    view=view
                )
            )
        return relationships

    async def _get_ontology(self, version: Version, view: OntologyViewMode) -> Ontology:
        entries: List[OntologyEntryOutput] = []
        relationships: List[OntologyRelationshipOutput] = []
        async with await self.session.begin_transaction() as tx:
            if view == OntologyViewMode.EDITORIAL:
                query = queries['ontology']['ontology_editorial']
            else:
                query = queries['ontology']['ontology_published']
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
        entries: List[OntologyEntryOutput] = []
        
        async with await self.session.begin_transaction() as tx:
            if entry_ids:
                if view == OntologyViewMode.EDITORIAL:
                    query = queries['ontology']['ontology_entries_editorial']
                else:
                    query = queries['ontology']['ontology_entries_published']
                params = {
                    'entry_ids': entry_ids,
                    'version': version.packed_version
                }
            elif labels:
                if view == OntologyViewMode.EDITORIAL:
                    query = queries['ontology']['ontology_entries_by_label_editorial']
                else:
                    query = queries['ontology']['ontology_entries_by_label_published']
                params = {
                    'labels': labels,
                    'version': version.packed_version
                }
            else:
                raise ValueError("Must specify entry_ids or labels")

            result: AsyncResult = await tx.run(query, **params)
            async for record in result:
                entries.append(self.record_to_entry(record, version, view))
        return entries
