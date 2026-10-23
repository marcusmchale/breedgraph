MATCH (entry:OntologyEntry)-[:HAS_LIFECYCLE]->(entry_lifecycle:OntologyLifecycle)
WHERE entry.id in $entry_ids
WITH
  entry,
  entry_lifecycle

OPTIONAL MATCH
  (source: OntologyEntry)-[:HAS_RELATIONSHIP]->(relationship: OntologyRelationship)-[:RELATES_TO]->(target: OntologyEntry),
  (relationship)-[:HAS_LIFECYCLE]->(relationship_lifecycle:OntologyLifecycle)
  WHERE (source = entry OR target = entry) AND (
    relationship_lifecycle.activated <= $version
    // a draft entry with its draft relationships: data cites a draft only once it is restored, until the next commit
    OR (entry_lifecycle.activated IS NULL AND relationship_lifecycle.drafted <= $version)
  ) AND (
    relationship_lifecycle.removed IS NULL OR relationship_lifecycle.removed > $version
    // or removed with the entry: data cites an entry as it stood when it was deprecated
    OR entry.id IN coalesce(relationship_lifecycle.deprecated_with, [])
  )

WITH entry, entry_lifecycle, collect(relationship {
    .*,
    source_id: source.id,
    source_label: [label IN labels(source) WHERE label <> 'OntologyEntry'][0],
    target_id: target.id,
    target_label: [label IN labels(target) WHERE label <> 'OntologyEntry'][0],
    relationship_type: [label IN labels(relationship) WHERE label <> 'OntologyRelationship'][0],
    lifecycle: relationship_lifecycle {.*}
}) AS relationships
RETURN
entry {
  .*,
  label: [label IN labels(entry) WHERE label <> 'OntologyEntry'][0],
  references: [
      (reference: Reference)-[ref_for:REFERENCE_FOR]->(entry)
      WHERE
          ref_for.added < $version
      AND
          (ref_for.removed IS NULL or ref_for.removed > $version)
      | reference.id
  ],
  lifecycle: entry_lifecycle {.*}
} AS entry,
[rel IN relationships WHERE rel.id IS NOT NULL] AS relationships
