MATCH
  (user:User {id: ($user)})
RETURN user {.*}
