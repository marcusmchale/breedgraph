MATCH
  (team: Team {id: $team})
SET team.name = $name, team.name_lower = $name_lower, team.fullname = $fullname
