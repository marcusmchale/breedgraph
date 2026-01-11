MATCH (root: Unit)-[:IN_POSITION]->(position:Position)-[:AT_LOCATION]->(location: Location)
WHERE location.id in $location_ids AND NOT (root)<-[:INCLUDES_UNIT]-(:Unit)
//WHERE (position.start is NULL OR position.start <= datetime.transaction())
//AND (position.END is NULL or position.end >= datetime.transaction())
WITH root
OPTIONAL MATCH (root)-[:INCLUDES_UNIT*]->(child:Unit)
WITH root, coalesce(collect(DISTINCT child), []) AS children
WITH root.id AS root_id, root + children AS block
UNWIND block AS unit

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

WITH
  root_id,
  unit {
    .*,
    subject: [(unit)-[:OF_SUBJECT]->(subject:Subject) | subject.id][0],
    germplasm: [(unit)-[:OF_GERMPLASM]->(germplasm:Germplasm) | germplasm.id][0],
    positions: positions,
    parent_ids: [(parent:Unit)-[:INCLUDES_UNIT]->(unit)|parent.id]
  } as unit

WITH root_id, collect(unit) as block
return block