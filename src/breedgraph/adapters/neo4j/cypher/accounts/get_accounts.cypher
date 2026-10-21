MATCH
  (user:User)
WHERE user.id in $user_ids
RETURN user {.*}
