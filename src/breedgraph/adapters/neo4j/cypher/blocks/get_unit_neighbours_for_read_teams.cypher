// The direct parents and children of the given units, each with a readable flag for the given read teams
// and minimum release, so a view can collapse edges across units the user cannot read without scanning the block.
UNWIND $unit_ids AS unit_id
MATCH (unit:Unit {id: unit_id})
CALL (unit) {
  MATCH (unit)-[:INCLUDES_UNIT]->(neighbour:Unit)
  RETURN neighbour, 1 AS direction
  UNION
  MATCH (neighbour:Unit)-[:INCLUDES_UNIT]->(unit)
  RETURN neighbour, 0 AS direction
}
CALL (neighbour) {
  OPTIONAL MATCH (neighbour)<-[:CONTROLS]-(control:Control)<-[:CONTROLS]-(:TeamUnits)<-[:CONTROLS]-(team:Team)
  WITH team, control
  ORDER BY team.id, control.sequence DESC
  WITH team, collect(control)[0] AS control
  WHERE team IS NULL OR NOT coalesce(control.ended, false)
  RETURN collect(team.id) AS team_ids, collect(control.release) AS releases
}
RETURN unit.id AS id, neighbour.id AS neighbour_id, direction,
  CASE
    WHEN size(team_ids) = 0 THEN true
    WHEN any(team_id IN team_ids WHERE team_id IN $read_teams) THEN true
    ELSE reduce(lowest = 2, release IN releases | CASE WHEN release < lowest THEN release ELSE lowest END) >= $minimum_release
  END AS readable
