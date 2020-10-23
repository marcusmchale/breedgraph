MATCH
  (u: User {
    email: toLower($email),
    confirmed: false
  })-[:SUBMITTED*]->(n)
DETACH DELETE
  u,n