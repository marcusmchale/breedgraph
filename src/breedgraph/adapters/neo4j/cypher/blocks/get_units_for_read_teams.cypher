// Units by id, each with the id of its block root, a readable flag from its current controls and the
// given read teams and minimum release, its direct parent and child ids, and positions only when readable.
// Edges are raw: the view collapses them across units the user cannot read (see get_hidden_units_in_block).
UNWIND $unit_ids AS unit_id
MATCH (unit:Unit {id: unit_id})

CALL (unit) {
  MATCH (root:Unit)-[:INCLUDES_UNIT*0..]->(unit)
  WHERE NOT (root)<-[:INCLUDES_UNIT]-(:Unit)
  RETURN root.id AS root_id LIMIT 1
}

CALL (unit) {
  OPTIONAL MATCH (unit)<-[:CONTROLS]-(control:Control)<-[:CONTROLS]-(:TeamUnits)<-[:CONTROLS]-(team:Team)
  WITH team, control
  ORDER BY team.id, control.sequence DESC
  WITH team, collect(control)[0] AS control
  WHERE team IS NULL OR NOT coalesce(control.ended, false)
  RETURN collect(team.id) AS team_ids, collect(control.release) AS releases
}

WITH unit, root_id,
  CASE
    WHEN size(team_ids) = 0 THEN true
    WHEN any(team_id IN team_ids WHERE team_id IN $read_teams) THEN true
    ELSE reduce(lowest = 2, release IN releases | CASE WHEN release < lowest THEN release ELSE lowest END) >= $minimum_release
  END AS readable

OPTIONAL CALL (unit) {
  MATCH (unit)-[:IN_POSITION]->(position:Position)-[:AT_LOCATION]->(location:Location)
  WITH
    position,
    location,
    coalesce(position.start, datetime('0001-01-01T00:00:00')) AS effectiveStart,
    coalesce(position.end, datetime('9999-12-31T23:59:59')) AS effectiveEnd
  ORDER BY effectiveStart ASC, effectiveEnd ASC
  RETURN collect(
    position {
      .*,
      location_id: location.id,
      layout_id: [(position)-[:IN_LAYOUT]->(layout:Layout) | layout.id][0]
    }
  ) AS positions
}

RETURN unit {
  .*,
  subject: [(unit)-[:OF_SUBJECT]->(subject:Subject) | subject.id][0],
  germplasm: [(unit)-[:OF_GERMPLASM]->(germplasm:Germplasm) | germplasm.id][0],
  positions: CASE WHEN readable THEN coalesce(positions, []) ELSE [] END,
  parents: [(parent:Unit)-[:INCLUDES_UNIT]->(unit) | parent.id],
  children: [(unit)-[:INCLUDES_UNIT]->(child:Unit) | child.id],
  root_id: root_id,
  readable: readable
} AS unit
