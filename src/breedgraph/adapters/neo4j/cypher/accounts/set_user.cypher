MATCH (user:User {
  id: $user_id
})
SET user += $props