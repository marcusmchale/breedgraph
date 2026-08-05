MATCH
  (source: OntologyEntry)-[:HAS_RELATIONSHIP]->(relationship: OntologyRelationship)-[:RELATES_TO]->(target: OntologyEntry),
  (relationship)-[:HAS_LIFECYCLE]->(relationship_lifecycle:OntologyLifecycle)
  WHERE (source.id in $entry_ids OR target.id in $entry_ids) AND
  relationship_lifecycle.activated <= $version AND (
    relationship_lifecycle.deprecated IS NULL OR relationship_lifecycle.deprecated > $version
  )

WITH relationship, relationship_lifecycle, source, target
OPTIONAL MATCH (relationship_patch: OntologyRelationshipPatch)-[for_rel:FOR_RELATIONSHIP]->(relationship)
  WHERE for_rel.version < $version

WITH relationship, relationship_lifecycle, source, target, relationship_patch, for_rel
ORDER BY for_rel.time

WITH relationship, relationship_lifecycle, source, target, collect(relationship_patch {.*}) as relationship_patches
return collect(relationship {
    .*,
    source_id: source.id,
    source_label: [label IN labels(source) WHERE label <> 'OntologyEntry'][0],
    target_id: target.id,
    target_label: [label IN labels(target) WHERE label <> 'OntologyEntry'][0],
    relationship_type: [label IN labels(relationship) WHERE label <> 'OntologyRelationship'][0],
    patches: relationship_patches,
    lifecycle: relationship_lifecycle {.*}
}) AS relationships
