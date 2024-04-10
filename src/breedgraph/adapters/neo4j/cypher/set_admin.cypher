MATCH (user:User {id: $user_id})
MATCH (team:Team {id: $team_id})
MERGE (user)-[admin :ADMIN]->(team)
SET
  admin.authorisation = $authorisation,
  admin.heritable = $heritable
