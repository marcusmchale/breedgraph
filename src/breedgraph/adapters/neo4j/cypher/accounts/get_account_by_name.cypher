MATCH
  (user:User {name_lower: ($name_lower)})

RETURN user {.*}
