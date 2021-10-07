MATCH
  (u:User {
    email:          toLower($email),
    email_verified: false
  })-[:SUBMITTED*]->(n)
DETACH DELETE
u, n