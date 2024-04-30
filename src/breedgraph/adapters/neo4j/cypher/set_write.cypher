MATCH (user:User {id: $user})
MATCH (team:Team {id: $team})
MERGE (user)-[write :WRITE]->(team)
SET
 write.authorisation = $authorisation,
 write.heritable = $heritable