MATCH (user:User)
WHERE user.ontology_role_requested <> user.ontology_role
RETURN
  user {
    id: user.id,
    name: user.name,
    fullname: user.fullname,
    email: user.email,
    ontology_role: user.ontology_role,
    ontology_role_requested: user.ontology_role_requested,
    email_verified: user.email_verified
  }