MATCH (user:User {id: $user_id})
MATCH (team:Team {id: $team_id})
MERGE (user)-[writes_for :WRITES_FOR]->(team)
ON CREATE SET
 writes_for.time = datetime.transaction(),
 writes_for.authorisation = $authorisation
