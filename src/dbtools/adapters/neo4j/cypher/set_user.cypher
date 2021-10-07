MATCH (user:User {
  id: $id
})
SET
user.username = $username,
user.username_lower = $username_lower,
user.password_hash = $password_hash,
user.email = $email,
user.fullname = $fullname,
user.email_verified = $email_verified,
user.allowed_emails = $emails,
user.global_admin = $global_admin