// A team controls an entity while its latest Control for that entity is not ended
MATCH (team: Team {id: $team_id})
RETURN EXISTS {
  MATCH (team)-[:CONTROLS]->(tp)-[:CONTROLS]->(control: Control)-[:CONTROLS]->(entity)
  WITH entity, control
  ORDER BY control.sequence DESC
  WITH entity, collect(control)[0] AS latest_control
  WHERE NOT coalesce(latest_control.ended, false)
  RETURN entity
} AS in_use
