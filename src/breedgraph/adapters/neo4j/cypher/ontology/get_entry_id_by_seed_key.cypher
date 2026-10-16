MATCH (entry: OntologyEntry {seed_key: $seed_key})
RETURN entry.id AS id
