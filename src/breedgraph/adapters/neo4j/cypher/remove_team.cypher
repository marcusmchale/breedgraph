MATCH (team: Team {id: $team})
DETACH DELETE team
