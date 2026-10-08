// Whether Persons can be contacts: linked to an account and not erased. Reveals no personal data.
UNWIND $person_ids AS person_id
OPTIONAL MATCH (person: Person {id: person_id})
RETURN
  person_id,
  person IS NOT NULL AS exists,
  person IS NOT NULL AND EXISTS { (:User)-[:IS_PERSON]->(person) } AS linked,
  person IS NOT NULL AND person.erased_at IS NOT NULL AS erased
