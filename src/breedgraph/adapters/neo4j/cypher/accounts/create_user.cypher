MERGE (counter:Counter {name: 'user'})
  ON CREATE SET counter.count = 0
SET counter.count = counter.count + 1
CREATE (user: User {
  name_lower: $name_lower,
  id:             counter.count,
  name:       $name,
  password_hash:  $password_hash,
  email:          $email,
  email_lower: $email_lower,
  fullname:       $fullname,
  email_verified: $email_verified,
  time:           datetime.transaction()
})
RETURN user {.*}