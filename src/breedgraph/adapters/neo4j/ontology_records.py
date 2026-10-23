"""
Ontology entries and relationships as read, from the records of the ontology queries: shared by the ontology view and,
for what data already cites (the referential view), by the ontology persistence in a unit of work.
"""
from collections import defaultdict
from dataclasses import fields
from typing import List, Optional, Tuple

from neo4j import Record

from breedgraph.domain.model.ontology import (
    Version, OntologyEntryLabel, ControlMethodType, ObservationMethodType, RecordGroupExtent, ScaleType, AxisType,
    OntologyRelationshipLabel, EntryLifecycle, RelationshipLifecycle, LifecyclePhase
)
from breedgraph.service_layer.queries.read_models import OntologyEntryOutput, OntologyViewMode, OntologyRelationshipOutput
from breedgraph.service_layer.mappers import ontology_mapper


def get_label_from_record(record: Record|dict):
    entry = record.get('entry', record)  # Fallback to record if no 'entry' key
    try:
        return OntologyEntryLabel(entry.get('label'))
    except TypeError:
        raise ValueError("Record does not contain a label field")
    except ValueError:
        raise ValueError(f"Label is not recognized as a valid ontology entry label: {entry.get('label')}")


def get_entry_class_from_record(record: Record|dict):
    label = get_label_from_record(record)
    entry_class = ontology_mapper.get_entry_output_class_mapping().get(label)
    if not entry_class:
        raise ValueError(f"No entry output class found for label: {label}")
    return entry_class


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
    if entry_dict.get('default_extent') is not None:
        entry_dict['default_extent'] = RecordGroupExtent(entry_dict['default_extent'])


def filter_dict(entry_dict: dict, node_class):
    # Filter entry_dict to only include fields that exist on the node class
    node_fields = {f.name for f in fields(node_class)}
    return {k: v for k, v in entry_dict.items() if k in node_fields}


def patch_values(patch) -> dict:
    """An entry patch's attributes, with those it clears as null: a patch node can't hold a null, so it lists them"""
    values = dict(patch)
    for key in values.pop('cleared', None) or []:
        values[key] = None
    return values


def shows_relationship(lifecycle: RelationshipLifecycle, entry_id: int, view: OntologyViewMode) -> bool:
    """
    A deprecated or removed relationship is left out, unless the view is referential and it was deprecated with the
    entry: data cites an entry as it stood when it was deprecated (domain/services/ontology_lifecycles.py).
    """
    if lifecycle.current_phase in [LifecyclePhase.DEPRECATED, LifecyclePhase.REMOVED]:
        return view is OntologyViewMode.REFERENTIAL and entry_id in lifecycle.deprecated_with
    return not (lifecycle.current_phase is LifecyclePhase.DRAFT and view is OntologyViewMode.PUBLISHED)


def record_to_entry(
        record: Record|dict,
        version: Version,
        view: OntologyViewMode
) -> OntologyEntryOutput:
    entry_class = get_entry_class_from_record(record)
    entry_dict = record.get('entry', {})
    entry_dict.pop('label', None)

    coerce_intrinsic_attributes(entry_dict)

    entry_patches = entry_dict.get('patches', [])
    for patch in entry_patches:
        entry_dict.update(patch_values(patch))

    entry_dict = filter_dict(entry_dict, entry_class)

    relationship_dicts = record.get('relationships', [])
    attr_rels = defaultdict(list)
    for relationship_dict in relationship_dicts:
        # To return fully hydrated views of the entries as nodes that incorporate relationship details.
        # This helps in preselecting values in forms and simplifying other interfaces
        # filter by lifecycles first
        lifecycle = RelationshipLifecycle(**relationship_dict.get('lifecycle'))
        if not shows_relationship(lifecycle, entry_dict['id'], view):
            continue
        # then add to map from attr to rel if not filtered out
        is_source = relationship_dict['source_id'] == entry_dict['id']
        attr = ontology_mapper.get_attribute_name(
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
        if attr_type in [tuple[int, ...], Optional[tuple[int, ...]], Tuple[int, ...], Optional[Tuple[int, ...]]]:
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
