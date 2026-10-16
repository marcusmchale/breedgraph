MERGE (counter: Counter {name: 'program'})
  ON CREATE SET counter.count = 0
SET counter.count = counter.count + 1
CREATE (program: Program {id: counter.count})
SET program += $program_data
WITH
  program
//Link contacts
CALL (program) {
  MATCH (contact: Person) WHERE contact.id in $contact_ids
  CREATE (program)-[has_contact:HAS_CONTACT]->(contact)
  RETURN
    collect(contact.id) AS contacts
}
//Link contributions: the Persons credited, with the roles they had
CALL (program) {
  UNWIND $contributions AS contribution
  MATCH (person: Person {id: contribution.person})
  CREATE (person)-[contributed:CONTRIBUTED_TO {roles: contribution.roles}]->(program)
  RETURN
    collect({person: person.id, roles: contributed.roles}) AS contributions
}
//Link references
CALL (program) {
  MATCH (reference: Reference) WHERE reference.id IN $reference_ids
  CREATE (reference)-[:REFERENCE_FOR ]->(program)
  RETURN
    collect(reference.id) AS references
}
RETURN
  program {
    .*,
    contact_ids: contacts,
    contributions: contributions,
    reference_ids: references
  }