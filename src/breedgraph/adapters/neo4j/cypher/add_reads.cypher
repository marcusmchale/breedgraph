MATCH (user:User {id: $user_id})
MATCH (team:Team {id: $team_id})
MERGE (user)-[reads_from :READS_FROM]->(team)
ON CREATE SET
  reads_from.time = datetime.transaction(),
  reads_from.authorisation = $authorisation
