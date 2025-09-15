MATCH (user: User {id: $user_id})
MATCH (entry: OntologyEntry) WHERE entry.id IN $entry_ids
SET entry.activated = $version
CREATE (user)-[:ACTIVATED {time:datetime.date.transaction()}]->(entry)