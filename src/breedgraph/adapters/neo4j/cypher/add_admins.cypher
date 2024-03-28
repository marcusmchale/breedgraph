MATCH (user:User {id: $user_id})
MATCH (team:Team {id: $team_id})
MERGE (user)-[admins_for :ADMINS_FOR]->(team)
ON CREATE SET
  admins_for.time = datetime.transaction(),
  admins_for.authorisation = $authorisation
