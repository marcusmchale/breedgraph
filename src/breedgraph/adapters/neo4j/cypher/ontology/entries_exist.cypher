UNWIND $entry_ids as entry_id
OPTIONAL MATCH (entry: OntologyEntry {id: entry_id})-[:HAS_LIFECYCLE]->(lifecycle:OntologyLifecycle) WHERE lifecycle.removed IS NULL
RETURN entry.id as id, entry IS NOT NULL as exists