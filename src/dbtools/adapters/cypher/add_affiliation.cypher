MATCH
  (user: User {username_lower: $username_lower})
MATCH
  (team: Team {name: $team_name})
MERGE (user)-[affiliation: AFFILIATED]->(team)
ON CREATE SET
  affiliation.time = datetime.transaction(),
  affiliation.level = 0
ON MATCH SET
  affiliation.level = $level