MATCH (user: User {id: $user_id})
MATCH (entry: OntologyEntry) WHERE entry.id IN $entry_ids
SET entry.deprecated = $version
CREATE (user)-[:DEPRECATED {time:datetime.date.transaction()}]->(entry)