MATCH
  (user:User {email_lower: ($email_lower)})

RETURN user {.*}
