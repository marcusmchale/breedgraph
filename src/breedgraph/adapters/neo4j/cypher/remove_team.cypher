MATCH (team: Team {id: $team_id})
DETACH DELETE team
