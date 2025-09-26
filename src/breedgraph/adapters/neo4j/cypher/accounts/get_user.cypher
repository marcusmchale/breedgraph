MATCH (user: User {id: $user_id})
RETURN user {.id, .name, .fullname, .email, .ontology_role}
