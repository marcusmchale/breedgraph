// The Persons credited for a file, data file or external data reference, with the roles they had
MATCH (reference: Reference {id: $reference_id})
CALL (reference) {
  MATCH (person: Person)-[contributed:CONTRIBUTED_TO]->(reference)
    WHERE NOT person.id IN [contribution IN $contributions | contribution.person]
  DELETE contributed
}
CALL (reference) {
  UNWIND $contributions AS contribution
  MATCH (person: Person {id: contribution.person})
  MERGE (person)-[contributed:CONTRIBUTED_TO]->(reference)
  SET contributed.roles = contribution.roles
}
