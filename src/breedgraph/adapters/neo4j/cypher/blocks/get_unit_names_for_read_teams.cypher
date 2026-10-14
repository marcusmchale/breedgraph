// The lightest read of units: id, name and germplasm, with the name redacted where the given read teams cannot read.
// For crediting records to units, where positions and structure are not shown.
UNWIND $unit_ids AS unit_id
MATCH (unit:Unit {id: unit_id})
CALL (unit) {
  OPTIONAL MATCH (unit)<-[:CONTROLS]-(control:Control)<-[:CONTROLS]-(:TeamUnits)<-[:CONTROLS]-(team:Team)
  WITH team, control
  ORDER BY team.id, control.sequence DESC
  WITH team, collect(control)[0] AS control
  WHERE team IS NULL OR NOT coalesce(control.ended, false)
  RETURN collect(team.id) AS team_ids, collect(control.release) AS releases
}
RETURN unit.id AS id, unit.name AS name,
  [(unit)-[:OF_GERMPLASM]->(germplasm:Germplasm) | germplasm.id][0] AS germplasm,
  CASE
    WHEN size(team_ids) = 0 THEN true
    WHEN any(team_id IN team_ids WHERE team_id IN $read_teams) THEN true
    ELSE reduce(lowest = 2, release IN releases | CASE WHEN release < lowest THEN release ELSE lowest END) >= $minimum_release
  END AS readable
