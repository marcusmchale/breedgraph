MATCH (entry: OntologyEntry {id: $entry_id})
SET entry.seed_key = $seed_key
