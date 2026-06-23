MATCH (entry:OntologyEntry)-[:HAS_LIFECYCLE]->(lifecycle:OntologyLifecycle)
WHERE entry.id in $entry_ids
WITH
  entry,
  lifecycle
OPTIONAL MATCH
  (source: OntologyEntry)-[:HAS_RELATIONSHIP]->(relationship: OntologyRelationship)-[:RELATES_TO]->(target: OntologyEntry),
  (relationship)-[:HAS_LIFECYCLE]->(relationship_lifecycle:OntologyLifecycle)
  WHERE (source = entry OR target = entry) AND (
    relationship_lifecycle.drafted <= $version AND
    (relationship_lifecycle.deprecated IS NULL OR relationship_lifecycle.deprecated > $version)
  )
WITH entry, lifecycle, collect({
    relationship_id: relationship.id,
    source_id: source.id,
    source_label: [label IN labels(source) WHERE label <> "OntologyEntry"][0],
    target_id: target.id,
    target_label: [label IN labels(target) WHERE label <> "OntologyEntry"][0],
    relationship_type: [label IN labels(relationship) WHERE label <> "OntologyRelationship"][0],
    properties: properties(relationship),
    lifecycle: relationship_lifecycle {.*}
}) AS relationships
RETURN
entry {
  .*,
  label: [label IN labels(entry) WHERE label <> 'OntologyEntry'][0],
  authors: [(author: Person)-[authored:AUTHORED]->(entry) | author.id ],
  references: [(reference: Reference)-[ref_for:REFERENCE_FOR]->(entry) | reference.id ],
  lifecycle: lifecycle {.*}
} AS entry,
[rel IN relationships WHERE rel.relationship_id IS NOT NULL] AS relationships
