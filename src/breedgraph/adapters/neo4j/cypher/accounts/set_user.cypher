MATCH (user:User {
  id: $props['id']
})
SET user += $props