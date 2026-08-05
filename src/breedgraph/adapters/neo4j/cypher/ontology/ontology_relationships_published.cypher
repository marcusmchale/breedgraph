MATCH
  (source: OntologyEntry)-[:HAS_RELATIONSHIP]->(relationship: OntologyRelationship)-[:RELATES_TO]->(target: OntologyEntry),
  (relationship)-[:HAS_LIFECYCLE]->(relationship_lifecycle:OntologyLifecycle)
  WHERE (source.id in $entry_ids OR target.id in $entry_ids) AND
  relationship_lifecycle.activated <= $version AND (
    relationship_lifecycle.deprecated IS NULL OR relationship_lifecycle.deprecated > $version
  )

return collect(relationship {
    .*,
    source_id: source.id,
    source_label: [label IN labels(source) WHERE label <> 'OntologyEntry'][0],
    target_id: target.id,
    target_label: [label IN labels(target) WHERE label <> 'OntologyEntry'][0],
    relationship_type: [label IN labels(relationship) WHERE label <> 'OntologyRelationship'][0],
    lifecycle: relationship_lifecycle {.*}
}) AS relationships
