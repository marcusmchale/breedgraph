MATCH (user:User {id: $user_id})
MATCH (team:Team {id: $team_id})
MERGE (user)-[read :READ]->(team)
SET
  read.authorisation = $authorisation,
  read.heritable = $heritable
