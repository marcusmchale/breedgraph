MATCH (entry: OntologyEntry {id: $entry_id})
SET entry += $params
WITH entry
// Link contributor
  CALL {
  WITH entry
  MATCH (user: User {id: $user_id})
  MERGE (user)-[c:CONTRIBUTED]->(contributions: UserOntologyContributions)
  CREATE (contributions)-[contributed:CONTRIBUTED {time:datetime.transaction()}]->(entry)
}
// Link authors
CALL {
  WITH entry
  OPTIONAL MATCH (author: Person)-[authored:AUTHORED]->(entry)
  WHERE NOT author.id in $authors
  DELETE authored
}
CALL { 
  WITH entry
  UNWIND $authors as author_id
  MATCH (author: Person {id: author_id})
  MERGE (author)-[authored:AUTHORED]->(entry)
  ON CREATE SET authored.time = datetime.transaction()
}
// Link References
CALL {
  WITH entry
  OPTIONAL MATCH (reference: Reference)-[ref_for:REFERENCE_FOR]->(entry)
  WHERE NOT reference.id in $references
  DELETE ref_for
}
CALL {
  WITH entry
  UNWIND $references as ref_id
  MATCH (reference: Reference {id: ref_id})
  MERGE (reference)-[ref_for:REFERENCE_FOR]->(entry)
  ON CREATE SET ref_for.time = datetime.transaction()      
}   
RETURN NULL 
  