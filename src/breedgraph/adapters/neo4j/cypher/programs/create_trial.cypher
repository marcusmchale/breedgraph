MATCH (program:Program {id:$program_id})
MERGE (counter: Counter {name: 'trial'})
  ON CREATE SET counter.count = 0
SET counter.count = counter.count + 1
CREATE (program)-[:HAS_TRIAL]->(trial: Trial {
  id:          counter.count,
  name:        $name,
  fullname:    $fullname,
  description: $description,
  start: datetime($start['str']),
  start_unit: datetime($start['unit']),
  start_step: datetime($start['step']),
  end: datetime($end['str']),
  end_unit: datetime($end['unit']),
  end_step: datetime($end['step'])
})
WITH
  trial
//Link contacts
CALL {
  WITH trial
  MATCH (contact: Person) WHERE contact.id in $contact_ids
  CREATE (trial)-[has_contact:HAS_CONTACT]->(contact)
  RETURN
    collect(contact.id) AS contacts
}
//Link references
CALL {
  WITH trial
  MATCH (reference: Reference) WHERE reference.id IN $reference_ids
  CREATE (reference)-[:REFERENCE_FOR ]->(trial)
  RETURN
    collect(reference.id) AS references
}
RETURN
  trial {
    .*,
    contact_ids: contacts,
    reference_ids: references
  }