MATCH
  (program: Program {id: $program_id})
SET program += $program_data
// Update contacts
WITH program
CALL {
  WITH program
  MATCH (program)-[has_contact:HAS_CONTACT]->(contact:Person)
    WHERE NOT contact.id in $contact_ids
  DELETE has_contact
}
CALL {
  WITH program
  MATCH (contact: Person) WHERE contact.id in $contact_ids
  MERGE (program)-[:HAS_CONTACT]->(contact)
}
//Update references
CALL {
  WITH program
  MATCH (reference:Reference)-[reference_for:REFERENCE_FOR]->(program)
    WHERE NOT reference.id IN $reference_ids
  DELETE reference_for
}
CALL {
  WITH program
  MATCH (reference: Reference) WHERE reference.id IN $reference_ids
  MERGE (reference)-[reference_for:REFERENCE_FOR]->(program)
}
RETURN NULL