MATCH (team:Team {name: $team_name})
MERGE (counter:Counter {name: 'user'})
  ON CREATE SET counter.count = 0
MERGE (user:User {
  username_lower: $username_lower
})
  ON CREATE SET
  counter.count = counter.count + 1,
  user.id = counter.count,
  user.username = $username,
  user.password_hash = $password_hash,
  user.email = $email,
  user.fullname = $fullname,
  user.time = datetime.transaction(),
  user.confirmed = $confirmed
MERGE (user)-[affiliation:AFFILIATED]->(team)
  ON CREATE SET
  affiliation.level = $affiliation_level,
  affiliation.time = datetime.transaction()
RETURN user
