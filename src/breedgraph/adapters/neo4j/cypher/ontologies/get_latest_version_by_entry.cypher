MATCH (entry: OntologyEntry {id: $entry_id})-[:IN_VERSION]->(version:OntologyVersion)
RETURN version {.*}
ORDER BY version.id DESCENDING
LIMIT 1
