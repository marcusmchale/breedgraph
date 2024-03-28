MATCH
  (u:User {
    email_lower: $email_lower,
    email_verified: false
  })
DETACH DELETE u