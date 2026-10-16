MATCH (user: User {id: $user_id})
MERGE (user)-[:CONTRIBUTED]->(contributions: UserOntologyContributions)
WITH contributions
MATCH (entry: OntologyEntry) WHERE entry.id IN $entry_ids
SET entry.locked = $locked
CREATE (contributions)
  -[:CONTRIBUTED {time: datetime.transaction()}]->(:OntologyEntryLock {locked: $locked})
  -[:FOR_ENTRY {time: datetime.transaction()}]->(entry)
