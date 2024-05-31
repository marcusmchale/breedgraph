MATCH (user:User {id: $user})
MATCH (team:Team {id: $team})
MERGE (user)-[curate :CURATE]->(team)
SET
  curate.authorisation = $authorisation,
  curate.heritable = $heritable
