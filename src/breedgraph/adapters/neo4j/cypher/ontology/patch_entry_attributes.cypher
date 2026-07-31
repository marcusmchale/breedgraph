MATCH (entry: OntologyEntry {id: $entry_id})
CALL (entry) {
  WITH entry WHERE size(keys(coalesce($params, {}))) > 0
  MATCH (user: User {id: $user_id})
  MERGE (user)-[c:CONTRIBUTED]->(contributions: UserOntologyContributions)
  CREATE (contributions)
    -[contributed:CONTRIBUTED {time:datetime.transaction()}]->(patch:OntologyEntryPatch)
    -[:FOR_ENTRY {version: $version, time:  datetime.transaction()}]->(entry)
  SET patch += $params
}
// Update authors
CALL (entry) {
  MATCH (author: Person)
  WHERE author.id IN $authors_added
  CREATE (author)-[:AUTHORED {added: $version}]->(entry)
}
CALL (entry) {
  MATCH (author: Person)-[authored:AUTHORED]->(entry)
  WHERE author.id IN $authors_removed
  SET authored.removed = $version
}
// Update references
CALL (entry) {
  MATCH (reference: Reference)
  WHERE reference.id IN $references_added
  CREATE (reference)-[:REFERENCE_FOR {added: $version}]->(entry)
}
CALL (entry) {
  MATCH (reference: Reference)-[ref_for:REFERENCE_FOR]->(entry)
  WHERE reference.id IN $references_removed
  SET ref_for.removed = $version
}