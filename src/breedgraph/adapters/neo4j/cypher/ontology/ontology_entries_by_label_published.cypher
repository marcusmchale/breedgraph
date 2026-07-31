MATCH (entry:OntologyEntry)-[:HAS_LIFECYCLE]->(entry_lifecycle:OntologyLifecycle)
WHERE [label IN labels(entry) WHERE label <> "OntologyEntry"][0] in $labels
AND entry_lifecycle.activated <= $version AND (
  entry_lifecycle.deprecated IS NULL or entry_lifecycle.deprecated >= $version
)
WITH
  entry,
  entry_lifecycle

OPTIONAL MATCH
  (source: OntologyEntry)-[:HAS_RELATIONSHIP]->(relationship: OntologyRelationship)-[:RELATES_TO]->(target: OntologyEntry),
  (relationship)-[:HAS_LIFECYCLE]->(relationship_lifecycle:OntologyLifecycle)
  WHERE (source = entry OR target = entry) AND
  relationship_lifecycle.activated <= $version AND (
    relationship_lifecycle.deprecated IS NULL OR relationship_lifecycle.deprecated >= $version
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
  authors: [
      (author: Person)-[authored:AUTHORED]->(entry)
      WHERE
          authored.added < $version
      AND
          (authored.removed IS NULL OR authored.removed > $version)
      | author.id
  ],
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
