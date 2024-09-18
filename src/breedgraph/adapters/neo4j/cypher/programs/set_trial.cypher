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
    WHERE NOT contact.id in $contacts
  DELETE has_contact
}
CALL {
  WITH trial
  MATCH (contact: Person) WHERE contact.id in $contacts
  MERGE (trial)-[:HAS_CONTACT]->(contact)
}
//Update references
CALL {
  WITH trial
  MATCH (reference:Reference)-[reference_for:REFERENCE_FOR]->(trial)
    WHERE NOT reference.id IN $references
  DELETE reference_for
}
CALL {
  WITH trial
  MATCH (reference: Reference) WHERE reference.id IN $references
  MERGE (reference)-[reference_for:REFERENCE_FOR]->(trial)
}
RETURN NULL