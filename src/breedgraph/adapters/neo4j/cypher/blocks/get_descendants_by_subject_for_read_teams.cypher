// Every unit below the given units that the given read teams can read, grouped by subject, as id and name only.
// For selecting all the units of a subject in a block at once, e.g. every tree of a field.
// Units the user cannot read are left out, as the units view leaves them out of the block structure; what lies
// below them is still found, as the view reconnects it to its readable ancestors.
MATCH (root:Unit)
WHERE root.id IN $unit_ids
MATCH (root)-[:INCLUDES_UNIT*1..]->(unit:Unit)
WITH DISTINCT unit
CALL (unit) {
  OPTIONAL MATCH (unit)<-[:CONTROLS]-(control:Control)<-[:CONTROLS]-(:TeamUnits)<-[:CONTROLS]-(team:Team)
  WITH team, control
  ORDER BY team.id, control.sequence DESC
  WITH team, collect(control)[0] AS control
  WHERE team IS NULL OR NOT coalesce(control.ended, false)
  RETURN collect(team.id) AS team_ids, collect(control.release) AS releases
}
WITH unit,
  CASE
    WHEN size(team_ids) = 0 THEN true
    WHEN any(team_id IN team_ids WHERE team_id IN $read_teams) THEN true
    ELSE reduce(lowest = 2, release IN releases | CASE WHEN release < lowest THEN release ELSE lowest END) >= $minimum_release
  END AS readable
WHERE readable
OPTIONAL MATCH (unit)-[:OF_SUBJECT]->(subject:Subject)
WITH subject.id AS subject, unit
ORDER BY unit.name, unit.id
RETURN subject, collect({id: unit.id, name: unit.name}) AS units
