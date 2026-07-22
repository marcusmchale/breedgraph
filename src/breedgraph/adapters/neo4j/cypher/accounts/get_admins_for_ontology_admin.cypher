MATCH (user:User)
WHERE user.id <> 1 AND user.ontology_role = 'admin'
RETURN
  user {
    id: user.id,
    name: user.name,
    fullname: user.fullname,
    ontology_role: user.ontology_role,
    ontology_role_requested: user.ontology_role_requested
  }