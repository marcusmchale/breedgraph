MATCH (user: User {id: $user_id})
MATCH (entry: OntologyEntry) WHERE entry.id IN $entry_ids
SET entry.removed = $version
CREATE (user)-[:REMOVED {time:datetime.date.transaction()}]->(entry)