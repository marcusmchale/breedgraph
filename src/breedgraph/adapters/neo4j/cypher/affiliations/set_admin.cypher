MATCH (user:User {id: $user})
MATCH (team:Team {id: $team})
MERGE (user)-[admin :ADMIN]->(team)
SET
  admin.authorisation = $authorisation,
  admin.heritable = $heritable,
  admin.heritable_requested = $heritable_requested
