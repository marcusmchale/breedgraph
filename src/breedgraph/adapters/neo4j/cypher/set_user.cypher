MATCH (user:User {
  id: $user
})
SET
user.name = $name,
user.name_lower = $name_lower,
user.fullname = $fullname,
user.email = $email,
user.email_lower = $email_lower,
user.email_verified = $email_verified,
user.password_hash = $password_hash
