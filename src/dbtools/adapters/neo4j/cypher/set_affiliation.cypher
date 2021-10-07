MATCH
  (user: User {id: $user_id})
MATCH
  (team: Team {id: $team_id})
MERGE (user)-[affiliation:AFFILIATED]->(team)
  ON CREATE SET
    affiliation.times = [x in range(1, size(affiliation.levels)) | datetime.transaction()],
    affiliation.levels = $levels
  ON MATCH SET
    affiliation.times = [affiliation.times] +
      [x in range(size(affiliation.levels)+1, size($levels)) | datetime.transaction()],
    affiliation.levels = $levels

