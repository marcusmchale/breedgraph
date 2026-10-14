// Every readable unit some datasets have records for, under a narrowing by time and, when units are given, to those
// units and everything below them, grouped by subject as id and name: for selecting all the recorded units of a
// subject at once, e.g. every measured tree of a field. Units the user cannot read are left out, with the same team
// and release test as the units view; the caller has kept only the datasets the user can read.
CALL () {
  WITH 1 AS _
  WHERE $unit_ids IS NULL
  UNWIND $dataset_ids AS dataset_id
  MATCH (:Dataset {id: dataset_id})-[:INCLUDES_RECORD]->(record:Record)-[:FOR_UNIT]->(unit:Unit)
  WHERE ($start IS NULL OR coalesce(record.end, record.start) >= $start)
    AND ($end IS NULL OR coalesce(record.start, record.end) <= $end)
  RETURN DISTINCT unit
  UNION
  WITH 1 AS _
  WHERE $unit_ids IS NOT NULL
  UNWIND $unit_ids AS selected_id
  MATCH (:Unit {id: selected_id})-[:INCLUDES_UNIT*0..]->(unit:Unit)<-[:FOR_UNIT]-(record:Record)<-[:INCLUDES_RECORD]-(dataset:Dataset)
  WHERE dataset.id IN $dataset_ids
    AND ($start IS NULL OR coalesce(record.end, record.start) >= $start)
    AND ($end IS NULL OR coalesce(record.start, record.end) <= $end)
  RETURN DISTINCT unit
}
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
