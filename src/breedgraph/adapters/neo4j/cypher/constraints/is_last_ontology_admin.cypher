MATCH (u:User {ontology_role: "ADMIN"})
WHERE u.id <> $user_id
RETURN count(u) = 0
