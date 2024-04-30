MATCH (user:User {id: $user})
MATCH (team:Team {id: $team})
MERGE (user)-[read :READ]->(team)
SET
  read.authorisation = $authorisation,
  read.heritable = $heritable
