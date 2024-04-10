MATCH (user:User {id: $user_id})
MATCH (team:Team {id: $team_id})
MERGE (user)-[write :WRITE]->(team)
SET
 write.authorisation = $authorisation,
 write.heritable = $heritable