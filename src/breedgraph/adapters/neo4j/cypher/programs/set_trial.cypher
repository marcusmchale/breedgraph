MATCH
  (trial: Trial {id: $id})
SET
  trial.name = $name,
  trial.fullname = $fullname,
  trial.description = $description,
  trial.start = datetime($start['str']),
  trial.start_unit = datetime($start['unit']),
  trial.start_step = datetime($start['step']),
  trial.end = datetime($end['str']),
  trial.end_unit = datetime($end['unit']),
  trial.end_step = datetime($end['step'])

// Update contacts
WITH trial
CALL {
  WITH trial
  MATCH (trial)-[has_contact:HAS_CONTACT]->(contact:Person)
    WHERE NOT contact.id in $contact_ids
  DELETE has_contact
}
CALL {
  WITH trial
  MATCH (contact: Person) WHERE contact.id in $contact_ids
  MERGE (trial)-[:HAS_CONTACT]->(contact)
}
//Update references
CALL {
  WITH trial
  MATCH (reference:Reference)-[reference_for:REFERENCE_FOR]->(trial)
    WHERE NOT reference.id IN $reference_ids
  DELETE reference_for
}
CALL {
  WITH trial
  MATCH (reference: Reference) WHERE reference.id IN $reference_ids
  MERGE (reference)-[reference_for:REFERENCE_FOR]->(trial)
}
RETURN NULL