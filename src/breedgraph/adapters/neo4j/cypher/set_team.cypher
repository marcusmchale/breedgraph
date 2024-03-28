MATCH
  (team: Team {id: $team_id})
OPTIONAL MATCH (team)-[contributes_to:CONTRIBUTES_TO]->(:Team)
DELETE contributes_to
SET team.name = $name, team.name_lower = $name_lower, team.fullname = $fullname