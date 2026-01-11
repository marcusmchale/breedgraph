MATCH
  (captured: Unit {id: $unit_id})
OPTIONAL MATCH (captured)-[:INCLUDES_UNIT*]-(extended:Unit)
WITH captured, coalesce(collect(DISTINCT extended), []) AS units
WITH captured + units AS block
UNWIND block AS unit
WITH DISTINCT unit

OPTIONAL CALL (unit) {
  MATCH (unit)-[:IN_POSITION]->(position:Position)-[AT_LOCATION]->(location:Location)
  WITH
    position,
    location,
    coalesce(position.start, datetime('0001-01-01T00:00:00')) AS effectiveStart,
    coalesce(position.
      end, datetime('9999-12-31T23:59:59')) AS effectiveEnd
    ORDER BY effectiveStart ASC, effectiveEnd ASC
  RETURN
    collect(
      position {
        .*,
        location_id:location.id,
        layout_id:[(position)-[:IN_LAYOUT]->(layout:Layout)|layout.id][0]
      }
    ) AS positions
}

RETURN unit {
  .*,
  subject: [(unit)-[:OF_SUBJECT]->(subject:Subject) | subject.id][0],
  germplasm: [(unit)-[:OF_GERMPLASM]->(germplasm:Germplasm) | germplasm.id][0],
  positions: positions,
  parent_ids: [(parent:Unit)-[:INCLUDES_UNIT]->(unit)|parent.id]
}