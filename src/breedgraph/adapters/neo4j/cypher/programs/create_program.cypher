MERGE (counter: Counter {name: 'program'})
  ON CREATE SET counter.count = 0
SET counter.count = counter.count + 1
CREATE (program: Program {
  id:          counter.count,
  name:        $name,
  fullname:    $fullname,
  description: $description
})
WITH
  program
//Link contacts
CALL {
  WITH program
  MATCH (contact: Person) WHERE contact.id in $contacts
  CREATE (program)-[has_contact:HAS_CONTACT]->(contact)
  RETURN
    collect(contact.id) AS contacts
}
//Link references
CALL {
  WITH program
  MATCH (reference: Reference) WHERE reference.id IN $references
  CREATE (reference)-[:REFERENCE_FOR ]->(program)
  RETURN
    collect(reference.id) AS references
}
RETURN
  program {
    .*,
    contacts: contacts,
    references: references
  }