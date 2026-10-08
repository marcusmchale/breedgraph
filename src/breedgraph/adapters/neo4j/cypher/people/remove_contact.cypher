MATCH (entity: Program|Trial {id: $entity_id})-[has_contact:HAS_CONTACT]->(:Person {id: $person_id})
WHERE $label IN labels(entity)
DELETE has_contact
RETURN count(has_contact) AS removed
