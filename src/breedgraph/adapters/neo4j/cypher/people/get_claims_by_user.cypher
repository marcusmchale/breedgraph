MATCH (:User {id: $user_id})-[claims: CLAIMS]->(person: Person)
RETURN person.id AS person_id, claims.time AS time
ORDER BY claims.time
