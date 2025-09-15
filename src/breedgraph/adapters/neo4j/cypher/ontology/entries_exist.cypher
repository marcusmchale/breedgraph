UNWIND $entry_ids as entry_id
OPTIONAL MATCH (entry: OntologyEntry {id: entry_id})
RETURN entry.id as id, entry IS NOT NULL as exists