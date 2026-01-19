MATCH (u:User {ontology_role: "admin"})
WHERE u.id <> $user_id
RETURN count(u) = 0