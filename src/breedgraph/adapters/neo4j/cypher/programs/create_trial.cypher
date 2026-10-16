MATCH (program:Program {id:$program_id})
MERGE (counter: Counter {name: 'trial'})
  ON CREATE SET counter.count = 0
SET counter.count = counter.count + 1
CREATE (program)-[:HAS_TRIAL]->(trial: Trial {id: counter.count})
SET trial += $trial_data
WITH
  trial
//Link contacts
CALL (trial) {
  MATCH (contact: Person) WHERE contact.id in $contact_ids
  CREATE (trial)-[has_contact:HAS_CONTACT]->(contact)
  RETURN
    collect(contact.id) AS contacts
}
//Link contributions: the Persons credited, with the roles they had
CALL (trial) {
  UNWIND $contributions AS contribution
  MATCH (person: Person {id: contribution.person})
  CREATE (person)-[contributed:CONTRIBUTED_TO {roles: contribution.roles}]->(trial)
  RETURN
    collect({person: person.id, roles: contributed.roles}) AS contributions
}
//Link references
CALL (trial) {
  MATCH (reference: Reference) WHERE reference.id IN $reference_ids
  CREATE (reference)-[:REFERENCE_FOR ]->(trial)
  RETURN
    collect(reference.id) AS references
}
RETURN
  trial {
    .*,
    contact_ids: contacts,
    contributions: contributions,
    reference_ids: references
  }