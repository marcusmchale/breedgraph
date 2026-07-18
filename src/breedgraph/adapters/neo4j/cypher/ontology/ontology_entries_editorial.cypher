MATCH (entry:OntologyEntry)-[:HAS_LIFECYCLE]->(entry_lifecycle:OntologyLifecycle)
WHERE entry.id in $entry_ids
AND entry_lifecycle.drafted <=$version AND (
  entry_lifecycle.removed IS NULL or entry_lifecycle.removed >= $version
)
WITH
  entry,
  entry_lifecycle

OPTIONAL MATCH (entry_patch: OntologyEntryPatch)-[for_entry:FOR_ENTRY]->(entry)
  WHERE for_entry.version <= $version

WITH entry, entry_lifecycle, entry_patch, for_entry
ORDER BY for_entry.time
WITH entry, entry_lifecycle, collect(entry_patch {.*}) as entry_patches

OPTIONAL MATCH
  (source: OntologyEntry)-[:HAS_RELATIONSHIP]->(relationship: OntologyRelationship)-[:RELATES_TO]->(target: OntologyEntry),
  (relationship)-[:HAS_LIFECYCLE]->(relationship_lifecycle:OntologyLifecycle)
  WHERE (source = entry OR target = entry) AND
  relationship_lifecycle.drafted <= $version AND (
    relationship_lifecycle.deprecated IS NULL OR relationship_lifecycle.deprecated > $version
  )

WITH entry, entry_lifecycle, entry_patches, relationship, relationship_lifecycle, source, target

OPTIONAL MATCH (relationship_patch: OntologyRelationshipPatch)-[for_rel:FOR_RELATIONSHIP]->(relationship)
  WHERE for_rel.version <= $version

WITH entry, entry_lifecycle, entry_patches, relationship, relationship_lifecycle, source, target, relationship_patch, for_rel
ORDER BY for_rel.time
WITH entry, entry_lifecycle, entry_patches, relationship, relationship_lifecycle, source, target, collect(relationship_patch {.*}) as relationship_patches

WITH entry, entry_lifecycle, entry_patches, collect(relationship {
    .*,
    source_id: source.id,
    source_label: [label IN labels(source) WHERE label <> 'OntologyEntry'][0],
    target_id: target.id,
    target_label: [label IN labels(target) WHERE label <> 'OntologyEntry'][0],
    relationship_type: [label IN labels(relationship) WHERE label <> 'OntologyRelationship'][0],
    patches: relationship_patches,
    lifecycle: relationship_lifecycle {.*}
}) AS relationships
RETURN
entry {
  .*,
  label: [label IN labels(entry) WHERE label <> 'OntologyEntry'][0],
  authors: [
      (author: Person)-[authored:AUTHORED]->(entry)
      WHERE
          authored.added <= $version
      AND
          (authored.removed IS NULL OR authored.removed > $version)
      | author.id
  ],
  references: [
      (reference: Reference)-[ref_for:REFERENCE_FOR]->(entry)
      WHERE
          ref_for.added <= $version
      AND
          (ref_for.removed IS NULL or ref_for.removed > $version)
      | reference.id
  ],
  patches: entry_patches,
  lifecycle: entry_lifecycle {.*}
} AS entry,
[rel IN relationships WHERE rel.id IS NOT NULL] AS relationships
