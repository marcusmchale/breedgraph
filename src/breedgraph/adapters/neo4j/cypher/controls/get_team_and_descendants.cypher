MATCH (team: Team {id: $team_id})
RETURN [team.id] + [(team)-[:INCLUDES_TEAM*]->(descendant: Team) | descendant.id] AS team_ids
