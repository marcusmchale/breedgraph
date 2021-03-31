MATCH (user:User {
  id: $id
})
SET
user.username = $username,
user.username_lower = $username_lower,
user.password_hash = $password_hash,
user.email = $email,
user.fullname = $fullname,
user.confirmed = $confirmed