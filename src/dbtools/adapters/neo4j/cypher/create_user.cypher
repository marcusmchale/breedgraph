MERGE (counter:Counter {name: 'user'})
  ON CREATE SET counter.count = 0
SET counter.count = counter.count + 1
CREATE (user: User {
  username_lower: $username_lower,
  id:             counter.count,
  username:       $username,
  password_hash:  $password_hash,
  email:          $email,
  fullname:       $fullname,
  email_verified: $email_verified,
  global_admin:   $global_admin,
  time:           datetime.transaction()
})
RETURN user