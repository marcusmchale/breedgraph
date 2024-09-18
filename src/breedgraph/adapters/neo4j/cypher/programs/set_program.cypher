MATCH
  (program: Program {id: $id})
SET
  program.name = $name,
  program.fullname = $fullname,
  program.description = $description
// Update contacts
WITH program
CALL {
  WITH program
  MATCH (program)-[has_contact:HAS_CONTACT]->(contact:Person)
    WHERE NOT contact.id in $contacts
  DELETE has_contact
}
CALL {
  WITH program
  MATCH (contact: Person) WHERE contact.id in $contacts
  MERGE (program)-[:HAS_CONTACT]->(contact)
}
//Update references
CALL {
  WITH program
  MATCH (reference:Reference)-[reference_for:REFERENCE_FOR]->(program)
    WHERE NOT reference.id IN $references
  DELETE reference_for
}
CALL {
  WITH program
  MATCH (reference: Reference) WHERE reference.id IN $references
  MERGE (reference)-[reference_for:REFERENCE_FOR]->(program)
}
RETURN NULL