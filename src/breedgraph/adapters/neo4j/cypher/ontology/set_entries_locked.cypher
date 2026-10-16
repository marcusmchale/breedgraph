MATCH (user: User {id: $user_id})
MERGE (user)-[:LOCKED]->(locks: UserOntologyLocks)
WITH locks
MATCH (entry: OntologyEntry) WHERE entry.id IN $entry_ids AND coalesce(entry.locked, false) <> $locked
SET entry.locked = $locked
CREATE (locks)-[:LOCKED {time: datetime.transaction(), locked: $locked}]->(entry)
