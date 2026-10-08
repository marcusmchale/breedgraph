// Programs and Trials listing a Person as a contact
MATCH (entity: Program|Trial)-[:HAS_CONTACT]->(:Person {id: $person_id})
RETURN [label IN labels(entity) WHERE label IN ['Program', 'Trial']][0] AS label, entity.id AS id
ORDER BY label, id
