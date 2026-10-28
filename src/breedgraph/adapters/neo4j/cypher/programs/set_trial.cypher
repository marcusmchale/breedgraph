MATCH
  (trial: Trial {id: $trial_id})
SET trial += $trial_data
// Update contacts
WITH trial
CALL (trial) {
  MATCH (trial)-[has_contact:HAS_CONTACT]->(contact:Person)
    WHERE NOT contact.id in $contact_ids
  DELETE has_contact
}
CALL (trial) {
  MATCH (contact: Person) WHERE contact.id in $contact_ids
  MERGE (trial)-[:HAS_CONTACT]->(contact)
}
//Update contributions
CALL (trial) {
  MATCH (person: Person)-[contributed:CONTRIBUTED_TO]->(trial)
    WHERE NOT person.id IN [contribution IN $contributions | contribution.person]
  DELETE contributed
}
CALL (trial) {
  UNWIND $contributions AS contribution
  MATCH (person: Person {id: contribution.person})
  MERGE (person)-[contributed:CONTRIBUTED_TO]->(trial)
  SET contributed.roles = contribution.roles
}
//Update references
CALL (trial) {
  MATCH (reference:Reference)-[reference_for:REFERENCE_FOR]->(trial)
    WHERE NOT reference.id IN $reference_ids
  DELETE reference_for
}
CALL (trial) {
  MATCH (reference: Reference) WHERE reference.id IN $reference_ids
  MERGE (reference)-[reference_for:REFERENCE_FOR]->(trial)
}
RETURN NULL