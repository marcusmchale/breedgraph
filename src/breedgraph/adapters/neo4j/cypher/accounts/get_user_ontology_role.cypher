MATCH (user: User {id: $user_id})
RETURN user.ontology_role